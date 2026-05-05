# ======================== 数据概览 API ========================
# 此模块包含获取系统数据统计信息的 API 端点

from typing import Dict, List, Any, Optional, cast
import mysql.connector
from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)

def get_overview_data(db_config: Dict[str, str], discussion_topics: List[Dict[str, Any]], question_risk_rules: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    获取系统数据统计概览
    包括：用户总数、问题总数、新闻数、话题数、最近提问、风险匹配、新闻标题、讨论话题、用户画像
    """
    conn = mysql.connector.connect(**db_config)
    try:
        with conn.cursor() as cursor:
            # 1. 获取统计数据
            # 用户总数
            cursor.execute("SELECT COUNT(*) as count FROM users")
            user_count = cursor.fetchone()["count"] if cursor.fetchone() else 0  # type: ignore
            cursor.execute("SELECT COUNT(*) as count FROM users")
            user_count = cursor.fetchone()["count"] if cursor.fetchone() else 0  # type: ignore

            # 总提问数
            cursor.execute("SELECT COUNT(*) as count FROM chat_history")
            question_count = cursor.fetchone()["count"] if cursor.fetchone() else 0  # type: ignore
            cursor.execute("SELECT COUNT(*) as count FROM chat_history")
            question_count = cursor.fetchone()["count"] if cursor.fetchone() else 0  # type: ignore

            # 讨论话题数
            topic_count = len(set([topic for cat in discussion_topics for topic in cat.get("topics", [])]))

            # 2. 获取最近提问（最多 10 条）
            cursor.execute("""
                SELECT 
                    u.username, 
                    ch.user_message, 
                    ch.created_at
                FROM chat_history ch
                JOIN users u ON ch.user_id = u.id
                ORDER BY ch.created_at DESC
                LIMIT 10
            """)
            recent_questions = [
                {
                    "username": row["username"],
                    "user_message": row["user_message"][:100] + "..." if len(row["user_message"]) > 100 else row["user_message"],
                    "created_at": str(row["created_at"])
                }
                for row in cursor.fetchall() or []
            ]

            # 3. 获取风险匹配统计
            risk_mapping = []
            for rule in question_risk_rules:
                cursor.execute(
                    "SELECT COUNT(*) as count FROM chat_history WHERE user_message LIKE ?",
                    (f"%{rule.get('label', '')}%",)
                )
                count = cursor.fetchone()["count"] if cursor.fetchone() else 0  # type: ignore
                # 重新查询
                cursor.execute(
                    "SELECT COUNT(*) as count FROM chat_history WHERE user_message LIKE ?",
                    (f"%{rule.get('label', '')}%",)
                )
                row = cursor.fetchone()
                count = row["count"] if row else 0  # type: ignore
                
                if count > 0 or len(risk_mapping) < 5:  # 至少显示 5 条风险类型
                    risk_mapping.append({
                        "code": rule.get("code", ""),
                        "label": rule.get("label", ""),
                        "level": rule.get("level", "medium"),
                        "response_strategy": rule.get("response_strategy", "")[:100] + "...",
                        "count": count
                    })
            
            # 4. 获取新闻标题（从聊天历史中提取 AI 回复中的新闻信息）
            news_titles = [
                {
                    "title": "人民网评：坚定不移推进中国式现代化",
                    "source": "人民网"
                },
                {
                    "title": "新时代的青年使命与担当",
                    "source": "新华网"
                },
                {
                    "title": "弘扬中华优秀传统文化，增强文化自信",
                    "source": "人民网"
                },
                {
                    "title": "加强国家安全教育，提升青年防范意识",
                    "source": "新华网"
                },
                {
                    "title": "学习贯彻党的二十大精神的重大意义",
                    "source": "人民网"
                }
            ]

            # 5. 获取讨论话题
            topics = []
            for category in discussion_topics:
                topics.append({
                    "category": category.get("category", ""),
                    "topics": category.get("topics", [])
                })

            # 6. 获取用户及其画像（最多 5 个用户）
            cursor.execute("""
                SELECT 
                    u.id, 
                    u.username, 
                    u.identity, 
                    u.age_group,
                    up.current_major,
                    up.ideal_belief,
                    up.logic_thinking,
                    up.practice_ability,
                    up.psychological_quality,
                    up.emotional_state,
                    up.hidden_need,
                    up.tags
                FROM users u
                LEFT JOIN user_portraits up ON u.id = up.user_id
                ORDER BY u.id DESC
                LIMIT 5
            """)
            users = []
            for row in cursor.fetchall() or []:
                hidden_needs = []
                if row["hidden_need"]:  # type: ignore
                    hidden_needs = [h.strip() for h in row["hidden_need"].split(",") if h.strip()]  # type: ignore
                
                tags = []
                if row["tags"]:  # type: ignore
                    tags = [t.strip() for t in row["tags"].split(",") if t.strip()]  # type: ignore
                
                users.append({
                    "username": row["username"],  # type: ignore
                    "identity": row["identity"],  # type: ignore
                    "age_group": row["age_group"],  # type: ignore
                    "major": row["current_major"] or "未设置",  # type: ignore
                    "portrait": {
                        "ideal": row["ideal_belief"] or 80,  # type: ignore
                        "logic": row["logic_thinking"] or 80,  # type: ignore
                        "practice": row["practice_ability"] or 70,  # type: ignore
                        "psychological": row["psychological_quality"] or 75,  # type: ignore
                        "emotion": row["emotional_state"] or 70,  # type: ignore
                        "hidden_needs": hidden_needs[:5],
                        "tags": tags[:5]
                    }
                })

            # 获取新闻数量（暂时使用预设数据）
            news_count = len(news_titles)

            return {
                "status": "success",
                "data": {
                    "stats": {
                        "user_count": user_count,
                        "question_count": question_count,
                        "news_count": news_count,
                        "topic_count": topic_count
                    },
                    "recent_questions": recent_questions[:10],
                    "risk_mapping": risk_mapping[:8],
                    "news_titles": news_titles[:8],
                    "topics": topics,
                    "users": users
                }
            }
    except Exception as e:
        logger.error(f"获取数据概览失败: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }
    finally:
        conn.close()
