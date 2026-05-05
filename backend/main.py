import json
import os
import re
import logging
from datetime import datetime
from html import unescape
from urllib.parse import urljoin, urlparse

# ======================== Hugging Face 国内镜像配置 ========================
# 必须在导入 transformers/sentence_transformers 之前设置环境变量
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
# 设置额外的环境变量以确保镜像生效
os.environ['HF_HOME'] = os.path.join(os.getcwd(), '.cache', 'huggingface')
os.environ['TRANSFORMERS_CACHE'] = os.path.join(os.getcwd(), '.cache', 'transformers')
os.environ['SENTENCE_TRANSFORMERS_HOME'] = os.path.join(os.getcwd(), '.cache', 'sentence_transformers')

import jieba.posseg as pseg  # 用于NLP预处理：分词与词性标注
from typing import Dict, Any, List, Optional, cast
from http import HTTPStatus
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import dashscope
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
import requests
import base64
import concurrent.futures
from openai import OpenAI
import sqlite3

# ======================== 基础配置 ========================
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="个性化思政教育交互系统", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 核心配置
DB_PATH = os.path.join(os.path.dirname(__file__), "data.db")
dashscope.api_key = "sk-d2df76fb2d91448f97dc3d6d7007169e"

# DeepSeek 大模型配置（使用 OpenAI 兼容接口）
DEEPSEEK_API_KEY = "sk-d6a467fa118048a8aed508f6de87ddfb"
DEEPSEEK_API_BASE = "https://api.deepseek.com"
DEEPSEEK_MODEL_ID = "deepseek-chat"  # DeepSeek 模型 ID

# 初始化 DeepSeek OpenAI 客户端
deepseek_client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_API_BASE)

# Kimi 大模型配置（使用 OpenAI 兼容接口）
KIMI_API_KEY = "sk-Yur62xHSg8AW7PZGK9hZvJLtXXoPUpuRNDoBq12OY0KMDi8V"
KIMI_API_BASE = "https://api.moonshot.cn/v1"
KIMI_MODEL_ID = "kimi-k2-turbo-preview"  # Kimi 模型 ID

# 初始化 Kimi OpenAI 客户端
kimi_client = OpenAI(api_key=KIMI_API_KEY, base_url=KIMI_API_BASE)

# BERT情感分析模型配置（使用中文情感分析模型）
try:
    BERT_MODEL_NAME = "uer/roberta-base-finetuned-jd-binary-chinese"  # 中文情感分析模型
    bert_tokenizer = AutoTokenizer.from_pretrained(BERT_MODEL_NAME)
    bert_model = AutoModelForSequenceClassification.from_pretrained(BERT_MODEL_NAME)
    bert_model.eval()
    logger.info("BERT情感分析模型加载成功")
except Exception as e:
    logger.warning(f"BERT模型加载失败，将仅使用大模型分析: {str(e)}")
    bert_tokenizer = None
    bert_model = None

# RAG向量化模型配置（全局初始化以提高性能）
try:
    from sentence_transformers import SentenceTransformer
    EMBEDDING_MODEL = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
    logger.info("RAG Embedding模型加载成功")
except Exception as e:
    logger.warning(f"RAG Embedding模型加载失败: {str(e)}")
    EMBEDDING_MODEL = None

# ======================== 数据模型 ========================
class AuthRequest(BaseModel):
    username: str
    password: str
    identity: str = "普通学生"
    age_group: str = "20-25岁"
    current_major: str = "计算机科学"


def resolve_user_role(identity: Optional[str]) -> str:
    normalized = (identity or "").strip()
    if normalized == "管理员" or normalized.lower() in {"admin", "administrator", "superadmin"}:
        return "admin"
    return "user"


def normalize_db_role(role_value: Optional[str], identity_value: Optional[str] = None) -> str:
    normalized_role = (role_value or "").strip().lower()
    if normalized_role in {"admin", "user"}:
        return normalized_role
    return resolve_user_role(identity_value)


def ensure_users_role_schema() -> None:
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SHOW COLUMNS FROM users LIKE 'role'")
            has_role = cursor.fetchone()

            if not has_role:
                logger.info("检测到 users 缺少 role 字段，开始补充字段")
                cursor.execute(
                    "ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'user' COMMENT '用户角色：admin/user' AFTER identity"
                )

            # 兼容历史数据：identity 为管理员语义时，将角色回填为 admin。
            cursor.execute(
                """
                UPDATE users
                SET role = 'admin'
                WHERE role = 'user'
                  AND (
                    identity = '管理员'
                    OR LOWER(TRIM(identity)) IN ('admin', 'administrator', 'superadmin')
                  )
                """
            )

            # 清洗异常角色值，确保只保留 admin/user。
            cursor.execute(
                """
                UPDATE users
                SET role = 'user'
                WHERE role IS NULL OR TRIM(role) = '' OR LOWER(TRIM(role)) NOT IN ('admin', 'user')
                """
            )
            conn.commit()
    except Exception as e:
        logger.error(f"初始化 users.role 字段失败: {str(e)}")
        conn.rollback()
        raise
    finally:
        conn.close()

class ChatRequest(BaseModel):
    username: str
    message: str
    conversation_id: Optional[int] = None


class ConversationCreateRequest(BaseModel):
    username: str
    title: Optional[str] = None


class DiscussionPostCreateRequest(BaseModel):
    username: str
    topic: str
    title: Optional[str] = None
    content: str


class DiscussionPostActionRequest(BaseModel):
    username: str


NEWS_SOURCES = [
    {
        "name": "人民网",
        "url": "http://politics.people.com.cn/GB/1024/index.html",   
        "allowed_domains": {"people.com.cn", "www.people.com.cn", "politics.people.com.cn", "cpc.people.com.cn", "edu.people.com.cn", "theory.people.com.cn"},
        "path_keywords": ["/n1/", "/GB/", "/2025/"],  
    },
    {
        "name": "新华网",
        "url": "https://www.xinhuanet.com/politics/",
        "allowed_domains": {"www.xinhuanet.com", "xinhuanet.com", "www.news.cn", "news.cn"},
        "path_keywords": ["/politics", "/comments", "/education", "/legal"],
    },
]

NEWS_TITLE_KEYWORDS = [
    "思政", "时政", "国家安全", "青年", "理论", "教育", "党建", "党史", "法治", "文化", "强国", "中国式现代化", "总书记", "人民防线"
]

NEWS_EXCLUDED_TITLES = [
    "首页", "客户端", "下载客户端", "网站地图", "English", "举报", "登录", "注册", "分享", "更多", "专题", "视频新闻", "友情链接"
]

INTEREST_KEYWORD_MAP = {
    "人工智能": ["人工智能", "AI", "算法", "算力", "科技", "创新"],
    "计算机": ["数字", "算法", "科技", "创新", "网络", "数据"],
    "软件": ["数字", "平台", "软件", "科技", "创新"],
    "数据": ["数据", "数字", "算力", "科技", "治理"],
    "网络": ["网络", "安全", "数字", "治理"],
    "信息安全": ["国家安全", "网络安全", "法治", "治理"],
    "心理": ["青年", "成长", "教育", "心理"],
    "教育": ["教育", "青年", "育人", "课堂", "思政"],
    "法学": ["法治", "法治", "依法", "国家安全", "治理"],
    "经济": ["高质量发展", "经济", "就业", "改革", "创新"],
    "管理": ["治理", "改革", "高质量发展", "作风"],
    "历史": ["党史", "文化", "红色", "传统"],
    "文学": ["文化", "青年", "教育", "阅读"],
    "哲学": ["理论", "思想", "文化", "价值"],
    "机械": ["制造", "工业", "科技", "创新"],
    "电子": ["芯片", "科技", "创新", "数字"],
}

DISCUSSION_TOPIC_CATEGORIES = [
    {
        "category": "红色传承与家国情怀",
        "topics": [
            "红色故事我来讲",
            "我心中的英雄",
            "我爱我的祖国",
            "我与祖国共成长",
            "红色基因代代传",
            "强国有我",
            "青春心向党",
            "感恩社会报效祖国",
        ],
    },
    {
        "category": "青年使命与理想担当",
        "topics": [
            "争做新时代好青年",
            "新时代青年使命",
            "青年榜样力量",
            "乡村振兴青年有为",
            "理想与信念",
            "做有担当的新时代青年",
        ],
    },
    {
        "category": "品德修养与志愿服务",
        "topics": [
            "学雷锋，在行动",
            "诚信伴我成长",
            "践行社会主义核心价值观",
            "志愿服务与奉献",
            "廉洁修身诚信做人",
        ],
    },
    {
        "category": "文化自信与民族团结",
        "topics": [
            "传统文化我传承",
            "文化自信从我做起",
            "民族团结一家亲",
        ],
    },
    {
        "category": "劳动实践与绿色生活",
        "topics": [
            "劳动最光荣",
            "保护环境，从我做起",
            "节约小标兵",
            "低碳生活绿色发展",
        ],
    },
    {
        "category": "法治安全与网络文明",
        "topics": [
            "法治教育",
            "国家安全青年有责",
            "网络文明青年先行",
        ],
    },
    {
        "category": "理论学习与时代精神",
        "topics": [
            "学习二十大精神",
        ],
    },
]

DISCUSSION_TOPIC_TO_CATEGORY = {
    topic: item["category"]
    for item in DISCUSSION_TOPIC_CATEGORIES
    for topic in item["topics"]
}

QUESTION_RISK_RULES = [
    {
        "code": "learning_attitude_negative",
        "label": "学习态度消极",
        "level": "medium",
        "patterns": [
            r"不想学(习)?了?",
            r"学不下去",
            r"不想上课",
            r"不想写作业",
            r"厌学",
            r"摆烂",
            r"躺平",
            r"读不进去",
            r"一点都不想碰书",
            r"上课听不进去",
            r"完全没学习动力",
            r"不想复习",
            r"看到书就烦",
            r"卷不动了",
            r"学废了",
            r"真的不想卷了",
            r"学得我想逃",
        ],
        "response_strategy": "先共情和鼓励，避免贴标签或责备；帮助用户拆解学习任务、恢复节奏感，并提供短期可执行的小目标。",
    },
    {
        "code": "exam_anxiety",
        "label": "考试焦虑明显",
        "level": "medium",
        "patterns": [
            r"考试.*紧张",
            r"一到考试.*慌",
            r"怕挂科",
            r"复习不完",
            r"考前焦虑",
            r"一考试就失眠",
            r"担心考砸",
            r"考试要完了",
            r"这次肯定挂了",
            r"一想到考试就慌",
            r"复习越看越慌",
        ],
        "response_strategy": "先缓解考试焦虑，避免单纯施压；优先帮助用户做复习拆解、时间分配和情绪稳定，强调先完成关键部分。",
    },
    {
        "code": "procrastination_risk",
        "label": "拖延失控倾向",
        "level": "medium",
        "patterns": [
            r"总是拖到最后",
            r"一直拖延",
            r"拖着不想做",
            r"越拖越不想做",
            r"明知道要做却不做",
            r"拖延症",
            r"总想晚点再说",
            r"不到最后不动",
            r"一拖再拖",
            r"每次都卡在开始",
        ],
        "response_strategy": "不要道德化评价拖延；帮助用户缩小任务颗粒度，先建立最小行动和外部约束，再逐步恢复执行感。",
    },
    {
        "code": "study_burnout",
        "label": "学习倦怠明显",
        "level": "medium",
        "patterns": [
            r"学什么都没感觉",
            r"越学越麻木",
            r"感觉学了也没用",
            r"对学习完全提不起兴趣",
            r"整个人对学习很麻木",
            r"已经学到没感觉了",
            r"学到恶心",
            r"脑子已经转不动了",
            r"越学越空",
            r"感觉自己快耗干了",
        ],
        "response_strategy": "优先判断是否存在长期透支和倦怠，避免继续加压；帮助用户先恢复基本节律，再重新建立学习目标和成就反馈。",
    },
    {
        "code": "psychological_stress",
        "label": "心理压力明显",
        "level": "medium",
        "patterns": [
            r"压力好大",
            r"特别焦虑",
            r"快崩溃",
            r"撑不住",
            r"很疲惫",
            r"好累",
            r"情绪很差",
            r"喘不过气",
            r"每天都好压抑",
            r"最近状态特别差",
            r"整个人很崩",
            r"心里堵得慌",
            r"绷不住了",
            r"破防了",
            r"emo了",
            r"心态炸了",
        ],
        "response_strategy": "优先安抚情绪，避免空泛说教；提供减压和求助建议，必要时鼓励联系老师、辅导员或心理咨询资源。",
    },
    {
        "code": "sleep_disorder_risk",
        "label": "睡眠紊乱风险",
        "level": "medium",
        "patterns": [
            r"睡不着",
            r"失眠",
            r"晚上睡不着",
            r"半夜总醒",
            r"作息全乱了",
            r"白天没精神",
            r"凌晨还睡不着",
            r"越想越睡不着",
            r"天天熬到很晚",
            r"作息彻底废了",
            r"晚上根本停不下来",
        ],
        "response_strategy": "先关注作息和情绪是否互相影响，避免只说“早点睡”；优先建议减少刺激、稳定睡前节律，并视情况建议寻求专业帮助。",
    },
    {
        "code": "interpersonal_withdrawal",
        "label": "人际退缩倾向",
        "level": "medium",
        "patterns": [
            r"不想跟任何人说话",
            r"不想社交",
            r"不想见人",
            r"跟室友相处不来",
            r"觉得自己融不进去",
            r"没有人理解我",
            r"不想和同学接触",
            r"只想一个人待着",
            r"谁都不想理",
            r"越来越不想开口",
        ],
        "response_strategy": "先承认人际压力的真实感受，不强迫用户立刻外向；建议从低压力沟通、边界表达和可信任对象开始恢复联系。",
    },
    {
        "code": "social_comparison_anxiety",
        "label": "同辈比较焦虑",
        "level": "medium",
        "patterns": [
            r"别人都比我强",
            r"一比较就很难受",
            r"同学都比我厉害",
            r"感觉自己被甩开了",
            r"身边的人都在进步",
            r"我好像最差",
            r"越看别人越焦虑",
        ],
        "response_strategy": "先降低用户被比较带来的挫败感，避免继续强化排名思维；帮助用户把注意力转回自身节奏、阶段目标和可控改进。",
    },
    {
        "code": "adaptation_difficulty",
        "label": "新环境适应困难",
        "level": "medium",
        "patterns": [
            r"不适应大学生活",
            r"刚来学校很不适应",
            r"换了环境很难受",
            r"适应不了现在的节奏",
            r"到新环境后状态很差",
            r"在学校总觉得别扭",
            r"新学期完全不在状态",
        ],
        "response_strategy": "先承认适应期的不稳定是常见现象，避免要求用户立刻正常化；建议从作息、同伴联系和日常节奏三个方面逐步重建熟悉感。",
    },
    {
        "code": "campus_conflict",
        "label": "校园关系冲突",
        "level": "medium",
        "patterns": [
            r"和室友闹矛盾",
            r"和同学吵架",
            r"宿舍关系很差",
            r"室友让我很烦",
            r"班里关系很僵",
            r"同学故意针对我",
            r"在宿舍待不下去",
            r"室友阴阳我",
            r"班里有人故意找事",
            r"天天在宿舍受气",
        ],
        "response_strategy": "避免煽动对立；先帮助用户区分情绪和事实，建议用低冲突表达、边界沟通和求助辅导员等方式降温处理。",
    },
    {
        "code": "bullying_or_exclusion_risk",
        "label": "疑似被排斥或欺凌",
        "level": "high",
        "patterns": [
            r"他们都孤立我",
            r"被排挤",
            r"被针对",
            r"被欺负",
            r"总有人故意嘲讽我",
            r"大家都在排斥我",
            r"被校园欺凌",
            r"被集体孤立",
            r"他们故意不带我",
            r"一直被嘲笑",
        ],
        "response_strategy": "优先肯定用户感受并强调不应独自承受；建议及时保留信息、寻求老师辅导员或学校支持渠道，不鼓励私下激烈对抗。",
    },
    {
        "code": "career_confusion",
        "label": "就业或发展迷茫",
        "level": "medium",
        "patterns": [
            r"不知道以后干什么",
            r"对未来很迷茫",
            r"找不到方向",
            r"不知道选什么工作",
            r"感觉前途很迷茫",
            r"不知道适合什么",
            r"不知道要不要考研",
            r"就业压力太大",
            r"未来一片空白",
            r"完全不知道下一步",
            r"越想未来越慌",
        ],
        "response_strategy": "避免直接灌输大道理；帮助用户先缩小选择范围，从兴趣、能力、现实机会三个维度拆解方向判断。",
    },
    {
        "code": "family_pressure",
        "label": "家庭压力明显",
        "level": "medium",
        "patterns": [
            r"家里给我压力很大",
            r"父母总是逼我",
            r"家里总拿我比较",
            r"父母不理解我",
            r"家里只看成绩",
            r"一和家里沟通就很累",
            r"被家里安排得喘不过气",
            r"家里一直管着我",
            r"回家就觉得压抑",
            r"父母总否定我",
        ],
        "response_strategy": "不要简单要求用户忍耐；帮助用户先理清压力来源，再考虑如何表达真实感受、设置边界或寻找中间支持者沟通。",
    },
    {
        "code": "financial_stress",
        "label": "经济压力明显",
        "level": "medium",
        "patterns": [
            r"没钱了",
            r"生活费不够",
            r"经济压力很大",
            r"想兼职但撑不住",
            r"学费压力",
            r"家里负担不起",
            r"最近特别缺钱",
            r"怕没钱吃饭",
            r"又不敢跟家里开口",
            r"手头已经撑不住了",
        ],
        "response_strategy": "先承认经济压力的现实性，不做空泛安慰；优先建议盘点紧急需求、校园资助和可行兼职路径，避免高风险借贷。",
    },
    {
        "code": "internet_addiction_risk",
        "label": "网络沉迷倾向",
        "level": "medium",
        "patterns": [
            r"刷手机停不下来",
            r"一直玩游戏",
            r"熬夜打游戏",
            r"短视频刷太多",
            r"控制不住玩手机",
            r"天天打游戏",
            r"晚上一直刷视频",
            r"手机一拿起来就停不下",
            r"每天都在短视频里耗着",
            r"一玩就停不下来",
        ],
        "response_strategy": "不要简单斥责自制力差；帮助用户识别触发场景，先减少连续沉迷时长，再建立替代行为和作息边界。",
    },
    {
        "code": "emotional_relationship_distress",
        "label": "情感关系受挫",
        "level": "medium",
        "patterns": [
            r"失恋",
            r"分手了",
            r"感情上很难受",
            r"被喜欢的人拒绝",
            r"谈恋爱影响状态",
            r"感情让我很痛苦",
            r"因为感情什么都做不下去",
            r"被冷暴力",
            r"对方不理我我就崩",
            r"谈个恋爱把自己搞垮了",
        ],
        "response_strategy": "先尊重情感受挫带来的失落，不贬低或简单说“想开点”；帮助用户稳定日常节律，避免把全部自我价值绑在关系结果上。",
    },
    {
        "code": "value_confusion",
        "label": "价值迷茫或意义感不足",
        "level": "medium",
        "patterns": [
            r"不知道努力有什么意义",
            r"感觉一切都没意义",
            r"不知道坚持为了什么",
            r"觉得做什么都空",
            r"找不到意义",
            r"感觉生活没有目标",
            r"不知道自己为什么要这么累",
            r"觉得每天都白过",
            r"活得很空",
            r"整天像在硬撑",
        ],
        "response_strategy": "不要直接灌输抽象口号；帮助用户把意义感问题落回当下生活、关系和可实现的小目标上，逐步重建方向感。",
    },
    {
        "code": "academic_integrity_risk",
        "label": "学业诚信风险",
        "level": "high",
        "patterns": [
            r"怎么作弊",
            r"帮我作弊",
            r"代写",
            r"抄作业",
            r"论文造假",
            r"怎么蒙混过关",
            r"怎么逃课不被发现",
        ],
        "response_strategy": "明确拒绝不诚信路径，强调学业诚信和后果；把对话引导回补救、复习、沟通和正当解决办法。",
    },
    {
        "code": "self_harm_risk",
        "label": "疑似自伤或极端表达风险",
        "level": "high",
        "patterns": [
            r"不想活了",
            r"活着没意思",
            r"想结束自己",
            r"想自杀",
            r"不如死了",
            r"想消失",
            r"不想再撑了",
            r"我死了算了",
            r"没有必要活着",
        ],
        "response_strategy": "立即采用安全优先的回应方式，明确表达关心，鼓励马上联系身边可信任的人、老师或专业心理援助；不要进行说教或冷处理。",
    },
    {
        "code": "illegal_or_harmful_intent",
        "label": "疑似违规或有害倾向",
        "level": "high",
        "patterns": [
            r"报复",
            r"打人",
            r"骗",
            r"作弊",
            r"攻击",
            r"搞破坏",
            r"威胁别人",
            r"整他",
            r"报复同学",
            r"泄露隐私",
        ],
        "response_strategy": "明确劝阻风险行为，强调后果和边界，并引导回到合法、理性、可求助的解决路径。",
    },
]


def sanitize_ai_text(text: str) -> str:
    """规范化模型输出的换行与空白，同时保留 Markdown 语法。"""
    if not text:
        return ""

    cleaned = text.replace("\r\n", "\n")
    cleaned = re.sub(r"\n{4,}", "\n\n\n", cleaned)
    return cleaned.strip()


def assess_question_risk(user_text: str, explicit_data: Optional[Dict[str, List[str]]] = None) -> Dict[str, Any]:
    """基于用户当前提问做本地风险判定，并生成回应策略。"""
    matched_items: List[Dict[str, str]] = []
    normalized_text = re.sub(r"\s+", "", user_text or "")

    for rule in QUESTION_RISK_RULES:
        for pattern in rule["patterns"]:
            if re.search(pattern, normalized_text, re.IGNORECASE):
                matched_items.append({
                    "code": rule["code"],
                    "label": rule["label"],
                    "level": rule["level"],
                    "matched_pattern": pattern,
                    "response_strategy": rule["response_strategy"],
                })
                break

    if explicit_data and explicit_data.get("explicit_topics"):
        topics = explicit_data.get("explicit_topics", [])
        if any(topic in {"学习", "作业", "考试", "课程", "成绩"} for topic in topics) and re.search(r"不想|学不下去|厌学|摆烂", normalized_text):
            if not any(item["code"] == "learning_attitude_negative" for item in matched_items):
                matched_items.append({
                    "code": "learning_attitude_negative",
                    "label": "学习态度消极",
                    "level": "medium",
                    "matched_pattern": "topic+negative_intent",
                    "response_strategy": "先共情和鼓励，避免贴标签或责备；帮助用户拆解学习任务、恢复节奏感，并提供短期可执行的小目标。",
                })

        if any(topic in {"考试", "复习", "成绩", "挂科"} for topic in topics) and re.search(r"慌|紧张|怕|焦虑|考砸|失眠", normalized_text):
            if not any(item["code"] == "exam_anxiety" for item in matched_items):
                matched_items.append({
                    "code": "exam_anxiety",
                    "label": "考试焦虑明显",
                    "level": "medium",
                    "matched_pattern": "topic+exam_anxiety",
                    "response_strategy": "先缓解考试焦虑，避免单纯施压；优先帮助用户做复习拆解、时间分配和情绪稳定，强调先完成关键部分。",
                })

        if any(topic in {"就业", "考研", "未来", "方向", "工作"} for topic in topics) and re.search(r"迷茫|不知道|没方向|焦虑", normalized_text):
            if not any(item["code"] == "career_confusion" for item in matched_items):
                matched_items.append({
                    "code": "career_confusion",
                    "label": "就业或发展迷茫",
                    "level": "medium",
                    "matched_pattern": "topic+career_confusion",
                    "response_strategy": "避免直接灌输大道理；帮助用户先缩小选择范围，从兴趣、能力、现实机会三个维度拆解方向判断。",
                })

    level_priority = {"low": 0, "medium": 1, "high": 2}
    highest_item = None
    for item in matched_items:
        if highest_item is None or level_priority[item["level"]] > level_priority[highest_item["level"]]:
            highest_item = item

    if highest_item is None:
        return {
            "detected": False,
            "risk_level": "low",
            "primary_label": "未识别到明显风险信号",
            "matched_items": [],
            "response_strategy": "正常进行个性化分析和建议，保持具体、自然、有支持感。",
        }

    return {
        "detected": True,
        "risk_level": highest_item["level"],
        "primary_label": highest_item["label"],
        "matched_items": matched_items,
        "response_strategy": highest_item["response_strategy"],
    }


def build_risk_prompt_block(risk_assessment: Optional[Dict[str, Any]]) -> str:
    """将风险判定结果转换为系统提示词块。"""
    if not risk_assessment:
        return ""

    matched_items = cast(List[Dict[str, str]], risk_assessment.get("matched_items") or [])
    matched_labels = [item.get("label", "") for item in matched_items if item.get("label")]
    matched_labels_json = json.dumps(matched_labels, ensure_ascii=False)

    return f"""

    【当前提问风险判定】
    - 是否检测到风险信号：{'是' if risk_assessment.get('detected') else '否'}
    - 风险等级：{risk_assessment.get('risk_level', 'low')}
    - 主要判定：{risk_assessment.get('primary_label', '未识别到明显风险信号')}
    - 命中的风险类别：{matched_labels_json}
    - 回应策略：{risk_assessment.get('response_strategy', '')}
    """

# ======================== 数据库工具函数 ========================
def get_db_connection():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row  # 使返回结果为字典样式
        logger.info("SQLite 数据库连接成功")
        return conn
    except sqlite3.Error as e:
        logger.error(f"数据库连接失败: {str(e)}")
        raise HTTPException(status_code=500, detail="数据库连接异常，请检查配置")


def generate_conversation_title(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if not cleaned:
        return "新对话"
    return f"{cleaned[:18]}..." if len(cleaned) > 18 else cleaned


def serialize_conversation(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": record.get("id"),
        "user_id": record.get("user_id"),
        "title": record.get("title") or "新对话",
        "created_at": str(record.get("created_at") or ""),
        "updated_at": str(record.get("updated_at") or ""),
        "message_count": int(record.get("message_count") or 0),
        "last_message": record.get("last_message") or ""
    }


def build_discussion_post_title(topic: str, content: str, custom_title: Optional[str] = None) -> str:
    cleaned_title = re.sub(r"\s+", " ", (custom_title or "")).strip()
    if cleaned_title:
        return cleaned_title[:80]

    cleaned_content = re.sub(r"\s+", " ", content or "").strip()
    if not cleaned_content:
        return topic

    summary = cleaned_content[:24]
    if len(cleaned_content) > 24:
        summary = f"{summary}..."
    return f"{topic} | {summary}"


def serialize_discussion_post(record: Dict[str, Any]) -> Dict[str, Any]:
    topic = str(record.get("topic") or "")
    return {
        "id": record.get("id"),
        "topic": topic,
        "category": DISCUSSION_TOPIC_TO_CATEGORY.get(topic, "未分类"),
        "title": record.get("title") or topic,
        "content": record.get("content") or "",
        "author": record.get("author") or "匿名用户",
        "created_at": str(record.get("created_at") or ""),
        "like_count": int(record.get("like_count") or 0),
        "report_count": int(record.get("report_count") or 0),
        "user_liked": bool(record.get("user_liked") or False),
        "user_reported": bool(record.get("user_reported") or False),
    }


def get_user_id_by_username(conn, username: str) -> int:
    with conn.cursor() as cursor:
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        user_res = cursor.fetchone()
        if not user_res:
            raise HTTPException(status_code=404, detail="用户不存在")
        return int(cast(Any, user_res).get("id"))


def get_discussion_post_by_id(conn, post_id: int) -> Dict[str, Any]:
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT id, user_id, topic, title, content, created_at, like_count, report_count FROM discussion_posts WHERE id = %s",
            (post_id,)
        )
        post = cursor.fetchone()
        if not post:
            raise HTTPException(status_code=404, detail="帖子不存在")
        return cast(Dict[str, Any], post)


def fetch_discussion_post_detail(conn, post_id: int, viewer_user_id: Optional[int] = None) -> Dict[str, Any]:
    with conn.cursor() as cursor:
        if viewer_user_id is None:
            cursor.execute(
                """
                SELECT
                    p.id,
                    p.topic,
                    p.title,
                    p.content,
                    p.created_at,
                    p.like_count,
                    p.report_count,
                    u.username AS author,
                    0 AS user_liked,
                    0 AS user_reported
                FROM discussion_posts p
                INNER JOIN users u ON u.id = p.user_id
                WHERE p.id = %s
                """,
                (post_id,)
            )
        else:
            cursor.execute(
                """
                SELECT
                    p.id,
                    p.topic,
                    p.title,
                    p.content,
                    p.created_at,
                    p.like_count,
                    p.report_count,
                    u.username AS author,
                    CASE WHEN l.id IS NULL THEN 0 ELSE 1 END AS user_liked,
                    CASE WHEN r.id IS NULL THEN 0 ELSE 1 END AS user_reported
                FROM discussion_posts p
                INNER JOIN users u ON u.id = p.user_id
                LEFT JOIN discussion_post_likes l ON l.post_id = p.id AND l.user_id = %s
                LEFT JOIN discussion_post_reports r ON r.post_id = p.id AND r.user_id = %s
                WHERE p.id = %s
                """,
                (viewer_user_id, viewer_user_id, post_id)
            )

        post = cursor.fetchone()
        if not post:
            raise HTTPException(status_code=404, detail="帖子不存在")
        return cast(Dict[str, Any], post)


def strip_html_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", "", unescape(text or ""))


def should_include_news_item(title: str, article_url: str, source: Dict[str, Any]) -> bool:
    normalized_title = re.sub(r"\s+", " ", title).strip()
    if len(normalized_title) < 8:
        return False

    if any(excluded in normalized_title for excluded in NEWS_EXCLUDED_TITLES):
        return False

    parsed_url = urlparse(article_url)
    if parsed_url.scheme not in {"http", "https"}:
        return False

    if parsed_url.netloc not in source["allowed_domains"]:
        return False

    return any(keyword in normalized_title for keyword in NEWS_TITLE_KEYWORDS) or any(
        keyword in parsed_url.path for keyword in source["path_keywords"]
    )


def extract_news_items_from_html(page_html: str, source: Dict[str, Any], limit: int = 6) -> List[Dict[str, str]]:
    seen_pairs = set()
    items: List[Dict[str, str]] = []

    for href, inner_html in re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', page_html, flags=re.IGNORECASE | re.DOTALL):
        article_url = urljoin(source["url"], href)
        title = strip_html_tags(inner_html)
        title = re.sub(r"\s+", " ", title).strip()

        if not should_include_news_item(title, article_url, source):
            continue

        key = (title, article_url)
        if key in seen_pairs:
            continue
        seen_pairs.add(key)

        items.append({
            "title": title,
            "url": article_url,
            "source": source["name"]
        })

        if len(items) >= limit:
            break

    return items


def fetch_daily_news(limit: int = 6) -> List[Dict[str, str]]:
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0 Safari/537.36"
    })

    collected: List[Dict[str, str]] = []
    seen_urls = set()

    for source in NEWS_SOURCES:
        try:
            response = session.get(source["url"], timeout=10)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding
            source_items = extract_news_items_from_html(response.text, source, limit=limit)
        except Exception as exc:
            logger.warning(f"抓取 {source['name']} 新闻失败: {str(exc)}")
            continue

        for item in source_items:
            if item["url"] in seen_urls:
                continue
            seen_urls.add(item["url"])
            collected.append(item)
            if len(collected) >= limit:
                return collected

    return collected


def extract_recommendation_keywords(portrait: Dict[str, Any]) -> List[str]:
    raw_keywords: List[str] = []

    learning_preference = cast(List[str], portrait.get("learning_preference") or [])
    hidden_needs = cast(List[str], portrait.get("hidden_needs") or [])
    current_major = str(portrait.get("current_major") or "")

    raw_keywords.extend(learning_preference)
    raw_keywords.extend(hidden_needs)
    if current_major and current_major != "未设置":
        raw_keywords.append(current_major)

    expanded_keywords: List[str] = []
    for keyword in raw_keywords:
        clean_keyword = re.sub(r"\s+", "", str(keyword))
        if not clean_keyword:
            continue
        expanded_keywords.append(clean_keyword)
        for trigger, mapped_keywords in INTEREST_KEYWORD_MAP.items():
            if trigger in clean_keyword:
                expanded_keywords.extend(mapped_keywords)

    seen = set()
    ordered_keywords = []
    for keyword in expanded_keywords:
        if keyword not in seen:
            seen.add(keyword)
            ordered_keywords.append(keyword)

    return ordered_keywords[:18]


def score_news_for_keywords(item: Dict[str, str], keywords: List[str]) -> Dict[str, Any]:
    title = item.get("title", "")
    source = item.get("source", "")
    article_text = f"{title} {source}"

    matched_keywords = [keyword for keyword in keywords if keyword and keyword in article_text]
    score = 0

    for keyword in matched_keywords:
        if keyword in title:
            score += 3
        else:
            score += 1

    if any(token in title for token in ["青年", "思政", "教育", "国家安全", "理论", "文化"]):
        score += 2

    scored_item: Dict[str, Any] = dict(item)
    scored_item["score"] = score
    scored_item["matched_keywords"] = matched_keywords[:4]
    return scored_item


def fetch_recommended_news_for_user(username: str, limit: int = 6) -> Dict[str, Any]:
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
            user_res = cursor.fetchone()
            if not user_res:
                raise HTTPException(status_code=404, detail="用户不存在")

            user_id = int(cast(Any, user_res).get("id"))
            portrait = get_user_portrait(user_id)

        keywords = extract_recommendation_keywords(portrait)
        candidate_news = fetch_daily_news(limit=max(limit * 3, 12))
        scored_news = [score_news_for_keywords(item, keywords) for item in candidate_news]
        scored_news.sort(key=lambda item: (item.get("score", 0), len(item.get("matched_keywords", []))), reverse=True)

        recommended_news = [item for item in scored_news if item.get("score", 0) > 0][:limit]
        if len(recommended_news) < limit:
            used_urls = {item["url"] for item in recommended_news}
            fallback_news = [item for item in scored_news if item["url"] not in used_urls][:limit - len(recommended_news)]
            recommended_news.extend(fallback_news)

        return {
            "portrait_keywords": keywords[:8],
            "news": recommended_news[:limit]
        }
    finally:
        conn.close()


def ensure_chat_conversation_schema() -> None:
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_conversations (
                    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '会话ID',
                    user_id INT NOT NULL COMMENT '用户ID',
                    title VARCHAR(255) NOT NULL DEFAULT '新对话' COMMENT '会话标题',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
                    INDEX idx_chat_conversations_user_id (user_id),
                    INDEX idx_chat_conversations_updated_at (updated_at),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='聊天会话表'
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
                    user_id INT NOT NULL COMMENT '用户ID，关联users表',
                    conversation_id INT DEFAULT NULL COMMENT '所属会话ID',
                    user_message TEXT NOT NULL COMMENT '用户发送的消息内容',
                    user_emotion_score DECIMAL(5,2) DEFAULT NULL COMMENT '用户情感评分(0-100)',
                    user_ideal_belief DECIMAL(5,2) DEFAULT NULL COMMENT '理想信念强度(0-100)',
                    user_logic_thinking DECIMAL(5,2) DEFAULT NULL COMMENT '逻辑思维能力(0-100)',
                    user_practice_ability DECIMAL(5,2) DEFAULT NULL COMMENT '实践能力(0-100)',
                    user_psychological_quality DECIMAL(5,2) DEFAULT NULL COMMENT '心理素质(0-100)',
                    user_hidden_needs TEXT DEFAULT NULL COMMENT '隐性需求，逗号分隔',
                    user_interest_themes TEXT DEFAULT NULL COMMENT '兴趣主题，逗号分隔',
                    ai_reply TEXT NOT NULL COMMENT 'AI回复内容',
                    ai_reply_score INT DEFAULT NULL COMMENT 'AI回复评分(0-100)',
                    ai_reply_feedback TEXT DEFAULT NULL COMMENT 'AI回复改进意见',
                    selected_model VARCHAR(50) DEFAULT NULL COMMENT '选择的模型(Qwen/DeepSeek/Kimi)',
                    qwen_score INT DEFAULT NULL COMMENT 'Qwen模型评分',
                    deepseek_score INT DEFAULT NULL COMMENT 'DeepSeek模型评分',
                    kimi_score INT DEFAULT NULL COMMENT 'Kimi模型评分',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                    INDEX idx_user_id (user_id),
                    INDEX idx_conversation_id (conversation_id),
                    INDEX idx_created_at (created_at),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户与AI聊天历史记录表'
            """)

            cursor.execute("SHOW COLUMNS FROM chat_history LIKE 'conversation_id'")
            has_conversation_id = cursor.fetchone()
            if not has_conversation_id:
                logger.info("检测到 chat_history 缺少 conversation_id，开始补充字段")
                cursor.execute("ALTER TABLE chat_history ADD COLUMN conversation_id INT NULL COMMENT '所属会话ID' AFTER user_id")
                cursor.execute("CREATE INDEX idx_chat_history_conversation_id ON chat_history (conversation_id)")
                conn.commit()

            cursor.execute("SELECT DISTINCT user_id FROM chat_history WHERE conversation_id IS NULL")
            legacy_users = cast(List[Dict[str, Any]], cursor.fetchall() or [])

            for user in legacy_users:
                user_id = int(cast(Any, user).get("user_id"))
                cursor.execute("SELECT id FROM chat_conversations WHERE user_id = %s AND title = %s ORDER BY id ASC LIMIT 1", (user_id, "历史对话"))
                legacy_conversation = cursor.fetchone()

                if legacy_conversation:
                    legacy_conversation_id = int(cast(Any, legacy_conversation).get("id"))
                else:
                    cursor.execute(
                        "INSERT INTO chat_conversations (user_id, title) VALUES (%s, %s)",
                        (user_id, "历史对话")
                    )
                    legacy_conversation_id = int(cursor.lastrowid or 0)

                cursor.execute(
                    "UPDATE chat_history SET conversation_id = %s WHERE user_id = %s AND conversation_id IS NULL",
                    (legacy_conversation_id, user_id)
                )

            conn.commit()
    except Exception as e:
        logger.error(f"初始化聊天会话结构失败: {str(e)}")
        conn.rollback()
        raise
    finally:
        conn.close()


def ensure_discussion_schema() -> None:
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS discussion_posts (
                    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '讨论帖ID',
                    user_id INT NOT NULL COMMENT '发帖用户ID',
                    topic VARCHAR(120) NOT NULL COMMENT '讨论主题',
                    title VARCHAR(255) NOT NULL COMMENT '帖子标题',
                    content TEXT NOT NULL COMMENT '帖子内容',
                    like_count INT NOT NULL DEFAULT 0 COMMENT '点赞数',
                    report_count INT NOT NULL DEFAULT 0 COMMENT '举报数',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                    INDEX idx_discussion_posts_topic_created_at (topic, created_at),
                    INDEX idx_discussion_posts_user_id (user_id),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户讨论区帖子表'
            """)

            cursor.execute("SHOW COLUMNS FROM discussion_posts LIKE 'like_count'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE discussion_posts ADD COLUMN like_count INT NOT NULL DEFAULT 0 COMMENT '点赞数' AFTER content")

            cursor.execute("SHOW COLUMNS FROM discussion_posts LIKE 'report_count'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE discussion_posts ADD COLUMN report_count INT NOT NULL DEFAULT 0 COMMENT '举报数' AFTER like_count")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS discussion_post_likes (
                    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '点赞记录ID',
                    post_id INT NOT NULL COMMENT '帖子ID',
                    user_id INT NOT NULL COMMENT '点赞用户ID',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '点赞时间',
                    UNIQUE KEY uniq_discussion_like (post_id, user_id),
                    INDEX idx_discussion_post_likes_user_id (user_id),
                    FOREIGN KEY (post_id) REFERENCES discussion_posts(id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='讨论帖点赞记录表'
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS discussion_post_reports (
                    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '举报记录ID',
                    post_id INT NOT NULL COMMENT '帖子ID',
                    user_id INT NOT NULL COMMENT '举报用户ID',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '举报时间',
                    UNIQUE KEY uniq_discussion_report (post_id, user_id),
                    INDEX idx_discussion_post_reports_user_id (user_id),
                    FOREIGN KEY (post_id) REFERENCES discussion_posts(id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='讨论帖举报记录表'
            """)
            conn.commit()
    except Exception as e:
        logger.error(f"初始化讨论区结构失败: {str(e)}")
        conn.rollback()
        raise
    finally:
        conn.close()


def create_conversation_for_user(conn, user_id: int, title: Optional[str] = None) -> Dict[str, Any]:
    with conn.cursor() as cursor:
        cursor.execute(
            "INSERT INTO chat_conversations (user_id, title) VALUES (%s, %s)",
            (user_id, title or "新对话")
        )
        conversation_id = int(cursor.lastrowid)
        conn.commit()
        cursor.execute(
            "SELECT id, user_id, title, created_at, updated_at FROM chat_conversations WHERE id = %s",
            (conversation_id,)
        )
        conversation = cursor.fetchone()
        return cast(Dict[str, Any], conversation)


def get_conversation_for_user(conn, user_id: int, conversation_id: int) -> Dict[str, Any]:
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT id, user_id, title, created_at, updated_at FROM chat_conversations WHERE id = %s AND user_id = %s",
            (conversation_id, user_id)
        )
        conversation = cursor.fetchone()
        if not conversation:
            raise HTTPException(status_code=404, detail="会话不存在")
        return cast(Dict[str, Any], conversation)


@app.on_event("startup")
async def startup_event() -> None:
    ensure_users_role_schema()
    ensure_chat_conversation_schema()
    ensure_discussion_schema()

def get_user_portrait(user_id: int) -> Dict[str, Any]:
    """获取用户的最新画像数据"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 获取最新的用户画像
            cursor.execute(
                "SELECT ideal_belief, logic_thinking, practice_ability, psychological_quality, emotional_state, hidden_need, tags, current_major FROM user_portraits WHERE user_id = %s ORDER BY id DESC LIMIT 1",
                (user_id,)
            )
            portrait = cursor.fetchone()
            
            if portrait:
                # 解析tags和hidden_need
                tags = portrait["tags"].split(",") if portrait["tags"] else []  # type: ignore
                hidden_needs = portrait["hidden_need"].split(",") if portrait["hidden_need"] else []  # type: ignore
                
                # 过滤空字符串并处理
                tags = [t.strip() for t in tags if t.strip()]
                hidden_needs = [h.strip() for h in hidden_needs if h.strip()]
                
                return {
                    "ideal": portrait["ideal_belief"] or 80,  # type: ignore
                    "logic": portrait["logic_thinking"] or 80,  # type: ignore
                    "practice": portrait["practice_ability"] or 70,  # type: ignore
                    "psychological": portrait["psychological_quality"] or 75,  # type: ignore
                    "emotion": portrait["emotional_state"] or 70,  # type: ignore
                    "learning_preference": tags[:6],  # 学习偏好/行为标签，前6个
                    "hidden_needs": hidden_needs[:6],  # 隐性需求，前6个
                    "current_major": portrait["current_major"] or "未设置"  # type: ignore
                }
            else:
                # 如果没有画像数据，返回默认值
                return {
                    "ideal": 80,
                    "logic": 80,
                    "practice": 70,
                    "psychological": 75,
                    "emotion": 70,
                    "learning_preference": [],
                    "hidden_needs": [],
                    "current_major": "未设置"
                }
    except Exception as e:
        logger.error(f"获取用户画像失败: {str(e)}")
        return {
            "ideal": 80,
            "logic": 80,
            "practice": 70,
            "psychological": 75,
            "emotion": 70,
            "learning_preference": [],
            "hidden_needs": [],
            "current_major": "未设置"
        }
    finally:
        conn.close()

# ======================== 接口路由 ========================
@app.post("/register", summary="用户注册")
async def register(data: AuthRequest) -> Dict[str, Any]:
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 检查用户名是否存在
            cursor.execute("SELECT id FROM users WHERE username = %s", (data.username,))
            if cursor.fetchone():
                return {"status": "fail", "message": "用户名已存在"}

            requested_role = resolve_user_role(data.identity)
            if requested_role == "admin":
                return {"status": "fail", "message": "管理员账号不支持自助注册，请联系系统维护人员创建"}

            identity_value = data.identity.strip() if data.identity and data.identity.strip() else "普通学生"
            
            # 直接存储密码（明文）
            cursor.execute(
                "INSERT INTO users (username, password, identity, role, age_group) VALUES (%s, %s, %s, %s, %s)",
                (data.username, data.password, identity_value, requested_role, data.age_group)
            )
            
            # 获取新用户的ID
            user_id = cursor.lastrowid
            
            # 创建初始用户画像记录
            cursor.execute(
                "INSERT INTO user_portraits (user_id, ideal_belief, logic_thinking, practice_ability, psychological_quality, emotional_state, hidden_need, tags, current_major, chat_content) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (user_id, 80, 80, 70, 75, 70, "等待分析...", "", data.current_major, "用户注册")
            )
            
            conn.commit()
            logger.info(f"用户 {data.username} 注册成功")
            return {"status": "success", "message": "注册成功"}
    
    except mysql.connector.Error as e:
        conn.rollback()  # 出错回滚
        logger.error(f"注册数据库错误: {str(e)}")
        return {"status": "error", "message": "数据库操作失败"}
    
    except Exception as e:
        logger.error(f"注册未知错误: {str(e)}")
        return {"status": "error", "message": "服务器内部错误"}
    
    finally:
        conn.close()

@app.post("/login", summary="用户登录")
async def login(data: AuthRequest) -> Dict[str, Any]:
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 查询用户
            cursor.execute("SELECT id, username, password, identity, role FROM users WHERE username = %s", (data.username,))
            user = cursor.fetchone()
            
            # 验证用户和密码（明文比较）
            if not user:
                return {"status": "fail", "message": "用户名不存在"}
            if data.password != user["password"]:  # type: ignore
                return {"status": "fail", "message": "密码错误"}

            stored_identity = str(cast(Any, user)["identity"] or "普通学生")
            stored_role = normalize_db_role(
                cast(Optional[str], cast(Any, user)["role"]),
                stored_identity
            )
            requested_role = resolve_user_role(data.identity)
            if requested_role != stored_role:
                expected_identity = "管理员" if stored_role == "admin" else "普通用户"
                return {"status": "fail", "message": f"账号类型不匹配，请使用{expected_identity}身份登录"}
            
            # 获取用户画像数据
            portrait_data = get_user_portrait(user["id"])  # type: ignore
            
            logger.info(f"用户 {data.username} 登录成功")
            return {
                "status": "success",
                "message": "登录成功",
                "data": {
                    "user_id": user["id"],  # type: ignore
                    "username": user["username"],  # type: ignore
                    "identity": stored_identity,
                    "role": stored_role,
                    "portrait": portrait_data
                }
            }
    
    except mysql.connector.Error as e:
        logger.error(f"登录数据库错误: {str(e)}")
        return {"status": "error", "message": "数据库操作失败"}
    
    except Exception as e:
        logger.error(f"登录未知错误: {str(e)}")
        return {"status": "error", "message": "服务器内部错误"}
    
    finally:
        conn.close()

@app.get("/chat/history", summary="获取用户聊天历史")
async def get_chat_history(username: str, limit: int = 50, offset: int = 0):
    """
    获取用户的聊天历史记录
    - username: 用户名
    - limit: 每次返回的记录数（默认50条）
    - offset: 偏移量，用于分页
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 获取用户ID
            cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
            user_res = cursor.fetchone()
            if not user_res:
                raise HTTPException(status_code=404, detail="用户不存在")
            
            user_id = user_res["id"]  # type: ignore
            
            # 查询聊天记录，按时间倒序
            cursor.execute("""
                SELECT 
                    id, user_message, ai_reply, 
                    user_emotion_score, user_hidden_needs,
                    ai_reply_score, ai_reply_feedback, selected_model,
                    qwen_score, deepseek_score, kimi_score,
                    created_at
                FROM chat_history 
                WHERE user_id = %s 
                ORDER BY created_at DESC 
                LIMIT %s OFFSET %s
            """, (user_id, limit, offset))  # type: ignore
            
            history = cursor.fetchall()

            history = cast(List[Dict[str, Any]], history)

            for record in history:
                if record.get("ai_reply"):
                    record["ai_reply"] = sanitize_ai_text(str(record["ai_reply"]))
            
            # 获取总记录数
            cursor.execute("SELECT COUNT(*) as total FROM chat_history WHERE user_id = %s", (user_id,))  # type: ignore
            total_res = cursor.fetchone()
            total = total_res["total"] if total_res else 0  # type: ignore
            
            return {
                "status": "success",
                "data": {
                    "history": history,
                    "total": total,
                    "limit": limit,
                    "offset": offset
                }
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取聊天历史失败: {str(e)}")
        return {"status": "error", "message": str(e)}
    finally:
        conn.close()


@app.get("/conversations", summary="获取用户会话列表")
async def get_conversations(username: str):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
            user_res = cursor.fetchone()
            if not user_res:
                raise HTTPException(status_code=404, detail="用户不存在")

            user_id = int(user_res["id"])  # type: ignore
            cursor.execute(
                """
                SELECT
                    c.id,
                    c.user_id,
                    c.title,
                    c.created_at,
                    c.updated_at,
                    COUNT(h.id) AS message_count,
                    SUBSTRING_INDEX(GROUP_CONCAT(h.user_message ORDER BY h.created_at DESC SEPARATOR '\\n'), '\\n', 1) AS last_message
                FROM chat_conversations c
                LEFT JOIN chat_history h ON h.conversation_id = c.id
                WHERE c.user_id = %s
                GROUP BY c.id, c.user_id, c.title, c.created_at, c.updated_at
                ORDER BY c.updated_at DESC, c.id DESC
                """,
                (user_id,)
            )
            conversations = [serialize_conversation(cast(Dict[str, Any], row)) for row in cursor.fetchall() or []]

            return {
                "status": "success",
                "data": {
                    "conversations": conversations
                }
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取会话列表失败: {str(e)}")
        return {"status": "error", "message": str(e)}
    finally:
        conn.close()


@app.post("/conversations", summary="创建新会话")
async def create_conversation(data: ConversationCreateRequest):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE username = %s", (data.username,))
            user_res = cursor.fetchone()
            if not user_res:
                raise HTTPException(status_code=404, detail="用户不存在")

        conversation = create_conversation_for_user(conn, int(user_res["id"]), data.title)  # type: ignore
        return {
            "status": "success",
            "data": {
                "conversation": serialize_conversation(conversation)
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建会话失败: {str(e)}")
        return {"status": "error", "message": str(e)}
    finally:
        conn.close()


@app.get("/conversations/{conversation_id}/messages", summary="获取指定会话消息")
async def get_conversation_messages(conversation_id: int, username: str):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
            user_res = cursor.fetchone()
            if not user_res:
                raise HTTPException(status_code=404, detail="用户不存在")

            user_id = int(user_res["id"])  # type: ignore
            get_conversation_for_user(conn, user_id, conversation_id)

            cursor.execute(
                """
                SELECT
                    id, conversation_id, user_message, ai_reply,
                    user_emotion_score, user_hidden_needs,
                    ai_reply_score, ai_reply_feedback, selected_model,
                    qwen_score, deepseek_score, kimi_score,
                    created_at
                FROM chat_history
                WHERE user_id = %s AND conversation_id = %s
                ORDER BY created_at ASC, id ASC
                """,
                (user_id, conversation_id)
            )
            records = cast(List[Dict[str, Any]], cursor.fetchall() or [])

            for record in records:
                if record.get("ai_reply"):
                    record["ai_reply"] = sanitize_ai_text(str(record["ai_reply"]))

            return {
                "status": "success",
                "data": {
                    "conversation_id": conversation_id,
                    "messages": records
                }
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取会话消息失败: {str(e)}")
        return {"status": "error", "message": str(e)}
    finally:
        conn.close()

@app.get("/chat/history/{chat_id}", summary="获取单条聊天记录详情")
async def get_chat_detail(chat_id: int):
    """
    获取单条聊天记录的详细信息
    - chat_id: 聊天记录ID
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    id, user_id, user_message, ai_reply,
                    user_emotion_score, user_ideal_belief,
                    user_logic_thinking, user_practice_ability,
                    user_psychological_quality, user_hidden_needs,
                    user_interest_themes, ai_reply_score,
                    ai_reply_feedback, selected_model,
                    qwen_score, deepseek_score, kimi_score,
                    created_at
                FROM chat_history 
                WHERE id = %s
            """, (chat_id,))  # type: ignore
            
            record = cursor.fetchone()
            
            if not record:
                raise HTTPException(status_code=404, detail="聊天记录不存在")

            record = cast(Dict[str, Any], record)
            if record.get("ai_reply"):
                record["ai_reply"] = sanitize_ai_text(str(record["ai_reply"]))
            
            return {
                "status": "success",
                "data": record
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取聊天记录详情失败: {str(e)}")
        return {"status": "error", "message": str(e)}
    finally:
        conn.close()


@app.get("/discussion/topics", summary="获取讨论区主题分类")
async def get_discussion_topics() -> Dict[str, Any]:
    return {
        "status": "success",
        "data": {
            "categories": DISCUSSION_TOPIC_CATEGORIES,
            "flat_topics": list(DISCUSSION_TOPIC_TO_CATEGORY.keys()),
        }
    }


@app.get("/discussion/posts", summary="按主题获取讨论帖")
async def get_discussion_posts(topic: str, username: Optional[str] = None, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
    normalized_topic = re.sub(r"\s+", " ", topic or "").strip()
    if normalized_topic not in DISCUSSION_TOPIC_TO_CATEGORY:
        raise HTTPException(status_code=400, detail="讨论主题不存在")

    conn = get_db_connection()
    try:
        viewer_user_id: Optional[int] = None
        if username:
            viewer_user_id = get_user_id_by_username(conn, username)

        with conn.cursor() as cursor:
            if viewer_user_id is None:
                cursor.execute(
                    """
                    SELECT
                        p.id,
                        p.topic,
                        p.title,
                        p.content,
                        p.created_at,
                        p.like_count,
                        p.report_count,
                        u.username AS author,
                        0 AS user_liked,
                        0 AS user_reported
                    FROM discussion_posts p
                    INNER JOIN users u ON u.id = p.user_id
                    WHERE p.topic = %s
                    ORDER BY p.created_at DESC, p.id DESC
                    LIMIT %s OFFSET %s
                    """,
                    (normalized_topic, limit, offset)
                )
            else:
                cursor.execute(
                    """
                    SELECT
                        p.id,
                        p.topic,
                        p.title,
                        p.content,
                        p.created_at,
                        p.like_count,
                        p.report_count,
                        u.username AS author,
                        CASE WHEN l.id IS NULL THEN 0 ELSE 1 END AS user_liked,
                        CASE WHEN r.id IS NULL THEN 0 ELSE 1 END AS user_reported
                    FROM discussion_posts p
                    INNER JOIN users u ON u.id = p.user_id
                    LEFT JOIN discussion_post_likes l ON l.post_id = p.id AND l.user_id = %s
                    LEFT JOIN discussion_post_reports r ON r.post_id = p.id AND r.user_id = %s
                    WHERE p.topic = %s
                    ORDER BY p.created_at DESC, p.id DESC
                    LIMIT %s OFFSET %s
                    """,
                    (viewer_user_id, viewer_user_id, normalized_topic, limit, offset)
                )
            posts = [serialize_discussion_post(cast(Dict[str, Any], row)) for row in cursor.fetchall() or []]

            cursor.execute("SELECT COUNT(*) AS total FROM discussion_posts WHERE topic = %s", (normalized_topic,))
            total_res = cursor.fetchone()
            total = int(cast(Any, total_res).get("total", 0)) if total_res else 0

        return {
            "status": "success",
            "data": {
                "topic": normalized_topic,
                "category": DISCUSSION_TOPIC_TO_CATEGORY[normalized_topic],
                "posts": posts,
                "total": total,
                "limit": limit,
                "offset": offset,
            }
        }
    finally:
        conn.close()


@app.post("/discussion/posts", summary="发布讨论帖")
async def create_discussion_post(data: DiscussionPostCreateRequest) -> Dict[str, Any]:
    normalized_topic = re.sub(r"\s+", " ", data.topic or "").strip()
    normalized_content = re.sub(r"\s+", " ", data.content or "").strip()

    if normalized_topic not in DISCUSSION_TOPIC_TO_CATEGORY:
        raise HTTPException(status_code=400, detail="讨论主题不存在")
    if not normalized_content:
        raise HTTPException(status_code=400, detail="帖子内容不能为空")

    conn = get_db_connection()
    try:
        user_id = get_user_id_by_username(conn, data.username)
        post_title = build_discussion_post_title(normalized_topic, normalized_content, data.title)

        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO discussion_posts (user_id, topic, title, content) VALUES (%s, %s, %s, %s)",
                (user_id, normalized_topic, post_title, normalized_content)
            )
            post_id = int(cursor.lastrowid or 0)
            conn.commit()

            cursor.execute(
                """
                SELECT
                    p.id,
                    p.topic,
                    p.title,
                    p.content,
                    p.like_count,
                    p.report_count,
                    p.created_at,
                    u.username AS author,
                    0 AS user_liked,
                    0 AS user_reported
                FROM discussion_posts p
                INNER JOIN users u ON u.id = p.user_id
                WHERE p.id = %s
                """,
                (post_id,)
            )
            created_post = cursor.fetchone()

        return {
            "status": "success",
            "message": "发布成功",
            "data": {
                "post": serialize_discussion_post(cast(Dict[str, Any], created_post or {}))
            }
        }
    finally:
        conn.close()


@app.post("/discussion/posts/{post_id}/like", summary="点赞或取消点赞讨论帖")
async def toggle_discussion_post_like(post_id: int, data: DiscussionPostActionRequest) -> Dict[str, Any]:
    conn = get_db_connection()
    try:
        user_id = get_user_id_by_username(conn, data.username)
        get_discussion_post_by_id(conn, post_id)

        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM discussion_post_likes WHERE post_id = %s AND user_id = %s",
                (post_id, user_id)
            )
            existing_like = cursor.fetchone()

            if existing_like:
                cursor.execute(
                    "DELETE FROM discussion_post_likes WHERE post_id = %s AND user_id = %s",
                    (post_id, user_id)
                )
                cursor.execute(
                    "UPDATE discussion_posts SET like_count = GREATEST(like_count - 1, 0) WHERE id = %s",
                    (post_id,)
                )
                action = "unliked"
                message = "已取消点赞"
            else:
                cursor.execute(
                    "INSERT INTO discussion_post_likes (post_id, user_id) VALUES (%s, %s)",
                    (post_id, user_id)
                )
                cursor.execute(
                    "UPDATE discussion_posts SET like_count = like_count + 1 WHERE id = %s",
                    (post_id,)
                )
                action = "liked"
                message = "点赞成功"

            conn.commit()

        post = serialize_discussion_post(fetch_discussion_post_detail(conn, post_id, user_id))
        return {
            "status": "success",
            "message": message,
            "data": {
                "action": action,
                "post": post,
            }
        }
    finally:
        conn.close()


@app.post("/discussion/posts/{post_id}/report", summary="举报讨论帖")
async def report_discussion_post(post_id: int, data: DiscussionPostActionRequest) -> Dict[str, Any]:
    conn = get_db_connection()
    try:
        user_id = get_user_id_by_username(conn, data.username)
        get_discussion_post_by_id(conn, post_id)

        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM discussion_post_reports WHERE post_id = %s AND user_id = %s",
                (post_id, user_id)
            )
            existing_report = cursor.fetchone()

            if existing_report:
                message = "你已举报过该帖子"
            else:
                cursor.execute(
                    "INSERT INTO discussion_post_reports (post_id, user_id) VALUES (%s, %s)",
                    (post_id, user_id)
                )
                cursor.execute(
                    "UPDATE discussion_posts SET report_count = report_count + 1 WHERE id = %s",
                    (post_id,)
                )
                conn.commit()
                message = "举报已提交"

        post = serialize_discussion_post(fetch_discussion_post_detail(conn, post_id, user_id))
        return {
            "status": "success",
            "message": message,
            "data": {
                "post": post,
            }
        }
    finally:
        conn.close()


@app.get("/news/daily", summary="获取每日实时思政新闻")
async def get_daily_news(limit: int = 6):
    try:
        safe_limit = max(1, min(limit, 10))
        news_items = fetch_daily_news(limit=safe_limit)
        return {
            "status": "success",
            "data": {
                "news": news_items,
                "updated_at": datetime.now().isoformat()
            }
        }
    except Exception as e:
        logger.error(f"获取每日新闻失败: {str(e)}")
        return {"status": "error", "message": "获取每日新闻失败，请稍后重试"}


@app.get("/news/recommended", summary="获取基于用户画像的新闻推荐")
async def get_recommended_news(username: str, limit: int = 6):
    try:
        safe_limit = max(1, min(limit, 10))
        recommendation_result = fetch_recommended_news_for_user(username=username, limit=safe_limit)
        return {
            "status": "success",
            "data": {
                "portrait_keywords": recommendation_result["portrait_keywords"],
                "news": recommendation_result["news"],
                "updated_at": datetime.now().isoformat()
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取推荐新闻失败: {str(e)}")
        return {"status": "error", "message": "获取推荐新闻失败，请稍后重试"}

# ======================== 核心画像逻辑模块 ========================

def nlp_pre_processing(text: str) -> Dict[str, List[str]]:
    """
    第一阶段：NLP预处理层
    执行分词、词性标注和实体识别，提取身份、专业、话题等基础属性
    """
    STOPWORDS = set([
    "的", "了", "是", "我", "你", "他", "她", "它", "们", "在", "有", "就", "不", "也", "还", 
    "这", "那", "个", "种", "类", "都", "而", "及", "与", "等", "和", "对", "对于", "关于"
    ])

    # 思政领域同义词典
    SYNONYM_DICT = {
    "二十大": ["党的二十大", "二十大报告"],
    "乡村振兴": ["乡村建设", "乡村发展", "三农"],
    "社会主义核心价值观": ["核心价值观", "价值观"],
    "党史学习": ["学党史", "党史教育", "党史"],
    "内卷": ["内耗", "过度竞争"],
    "焦虑": ["压力大", "迷茫", "困惑"],
    "自立自强": ["自主创新", "科技自立", "核心技术"]
    }

    words = pseg.cut(text)
    identities = []  # 身份提取
    topics = []      # 话题提取
    
    # 定义简单的思政相关词库（实际可扩展为知识图谱词库）
    identity_keywords = {'学生', '党员', '积极分子', '预备党员','团员', '青年','思政课代表','思政老师', '教师', '辅导员', '志愿者'}
    politics_topics = []  # 改为list以支持extend和append
    
    for word, flag in words:
        # n: 名词, nz: 专有名词
        if flag in ['n', 'nz'] and len(word) > 1 and word not in STOPWORDS:
            if word in identity_keywords:
                identities.append(word)
            else:
                if word in SYNONYM_DICT:
                    politics_topics.extend(SYNONYM_DICT[word])
                elif word in politics_topics:
                    politics_topics.append(word)
                else:
                    topics.append(word)
    
    return {
        "identities": list(set(identities)),
        "politics_topics": list(set(topics)),
        "explicit_topics": list(set(topics))
    }

def dynamic_semantic_completion(text: str) -> List[str]:
    """
    第三阶段：动态语义补全机制
    结合上下文语境推断隐性需求，解决表达模糊性
    """
    completion_rules = {
        r"资源.*(零散|乱|杂|找不到)": "对结构化知识体系的需求",
        r"(迷茫|不知道|困惑|无方向)": "对个性化生涯规划引导的需求",
        r"(内卷|压力|焦虑|疲惫)": "对心理疏导与价值观重塑的需求",
        r"(自立自强|核心技术|科技)": "对科技报国志向的强化需求",
        r"(党史|学习|了解)": "对系统化理论学习的需求",
        r"(乡村|农村|农民)": "对乡村振兴政策理解的需求"
    }
    hidden_needs = []
    for pattern, need in completion_rules.items():
        if re.search(pattern, text):
            hidden_needs.append(need)
    return hidden_needs

# ======================== 核心接口 ========================

# ======================== BERT情感分析辅助函数 ========================

def analyze_sentiment_with_bert(text: str) -> Dict[str, Any]:
    """
    使用BERT模型分析文本情感
    返回情感得分和置信度
    """
    if bert_tokenizer is None or bert_model is None:
        return {"sentiment_score": None, "confidence": 0.0, "label": "未知"}
    
    try:
        # 文本预处理和tokenization
        inputs = bert_tokenizer(text, return_tensors="pt", truncation=True, max_length=512, padding=True)
        
        # 模型推理
        with torch.no_grad():
            outputs = bert_model(**inputs)
            logits = outputs.logits
            probs = torch.softmax(logits, dim=-1)
            
        # 获取预测结果
        predicted_class = torch.argmax(probs, dim=-1).item()
        confidence = probs[0][predicted_class].item()
        
        # 将二分类结果映射到0-100分数（0=负面，1=正面）
        if predicted_class == 1:  # 正面情感
            sentiment_score = 50 + int(confidence * 50)  # 50-100
            label = "积极"
        else:  # 负面情感
            sentiment_score = 50 - int(confidence * 50)  # 0-50
            label = "消极"
        
        logger.info(f"BERT情感分析: score={sentiment_score}, label={label}, confidence={confidence:.2f}")
        
        return {
            "sentiment_score": sentiment_score,
            "confidence": round(confidence, 3),
            "label": label
        }
    except Exception as e:
        logger.error(f"BERT情感分析失败: {str(e)}")
        return {"sentiment_score": None, "confidence": 0.0, "label": "分析失败"}

# ======================== 第一阶段：用户画像补全与情感量化 ========================

def enhance_user_portrait(user_text: str, user_identity: str, user_age_group: str, historical_context: Dict[str, Any], explicit_data: Dict[str, List[str]]) -> Dict[str, Any]:
    """
    第一次调用大模型：补全完善用户画像、进行情感量化
    输入：用户文本、NLP提取的显性特征、历史画像、基本信息
    输出：补全后的用户画像（包含情感量化、兴趣主题、隐性需求等）
    """
    # 使用BERT进行情感分析
    bert_sentiment = analyze_sentiment_with_bert(user_text)
    
    rule_needs = historical_context.get("rule_based_needs", [])
    rule_needs_str = "、".join(rule_needs) if rule_needs else "未检测到特定触发词"
    
    # 构造BERT分析结果描述
    bert_info = ""
    if bert_sentiment["sentiment_score"] is not None:
        bert_label = bert_sentiment['label']
        bert_score = bert_sentiment['sentiment_score']
        bert_conf = bert_sentiment['confidence']
        bert_info = f"""
    【BERT情感分析结果】（客观机器学习模型分析）
    - 情感倾向：{bert_label}
    - 情感得分：{bert_score}/100
    - 置信度：{bert_conf*100:.1f}%
    （注意：此为BERT模型的初步判断，请结合语境综合分析）
        """
    
    # 预处理 JSON 字符串，避免 f-string 格式化错误
    identities_json = json.dumps(explicit_data.get('identities', []))
    politics_topics_json = json.dumps(explicit_data.get('politics_topics', []))
    explicit_topics_json = json.dumps(explicit_data.get('explicit_topics', []))
    historical_tags_json = json.dumps(historical_context.get('historical_tags', []))
    historical_hidden_needs_json = json.dumps(historical_context.get('historical_hidden_needs', []))
    
    # 构造第一阶段的系统提示词
    system_prompt_stage1 = f"""
    你现在是思政教育系统的用户画像分析专家。
    
    【用户基本信息】
    - 身份：{user_identity}
    - 年龄段：{user_age_group}
    - BERT模型情感分析结果：{bert_info}
    【NLP提取的显性特征】
    - 身份关键词：{identities_json}
    - 政治话题：{politics_topics_json}
    - 话题关键词：{explicit_topics_json}

    【本地规则识别到的潜在需求】
    - 预警信号：{rule_needs_str} 
    （注意：这是基于正则匹配的初步结果，请你结合语境判断其真实深度）
    
    【历史画像参考】
    - 历史标签：{historical_tags_json}
    - 历史隐性需求：{historical_hidden_needs_json}
    
    现在请对用户的新消息进行深度分析，输出完善的用户画像信息。
    
    分析维度包括：
    1. 情感量化：分析用户的情感状态，分别量化理想信念强度(0-100)、逻辑思维能力(0-100)、实践能力(0-100)、心理素质(0-100)、情感状态(0-100)
    2. 兴趣主题：识别用户的深层兴趣主题
    3. 隐性需求：推断用户未明确表达的隐性需求
    4. 用户标签：总结用户的多维度标签（身份、行为、情感等）
    
    必须严格返回 JSON 格式，不包含其他内容：
    {{
      "sentiment_score": 50-100,
      "logic_score": 50-100,
      "practice_ability": 50-100,
      "psychological_quality": 50-100,
      "emotional_state": 50-100,
      "interest_themes": ["主题1", "主题2", "主题3"],
      "hidden_needs": ["需求1", "需求2"],
      "user_tags": ["标签1", "标签2", "标签3"],
      "analysis_summary": "用户画像分析总结"
    }}
    """
    
    # 第一次调用大模型
    logger.info("第一阶段：调用大模型进行用户画像补全与情感量化...")
    response1 = dashscope.Generation.call(
        model=dashscope.Generation.Models.qwen_turbo,
        messages=[  # type: ignore
            {"role": "system", "content": system_prompt_stage1},
            {"role": "user", "content": user_text}
        ],
        result_format="message"
    )
    
    if response1.status_code != HTTPStatus.OK:  # type: ignore
        raise Exception("第一阶段大模型API调用失败")
    
    portrait_data = json.loads(response1.output.choices[0]["message"]["content"])  # type: ignore
    # 兼容旧模型输出，补齐新增画像维度
    portrait_data.setdefault("practice_ability", portrait_data.get("logic_score", 70))
    portrait_data.setdefault("psychological_quality", portrait_data.get("sentiment_score", 70))
    portrait_data.setdefault("emotional_state", portrait_data.get("sentiment_score", 70))
    logger.info(f"第一阶段完成：{repr(portrait_data)}")
    
    return portrait_data

# ======================== 第二阶段：基于完善画像的个性化回答 ========================

def build_personalized_system_prompt(
    portrait_data: Dict[str, Any],
    user_identity: str,
    user_age_group: str,
    user_major: str,
    explicit_data: Dict[str, List[str]],
    risk_assessment: Optional[Dict[str, Any]] = None
) -> str:
    # 预处理 JSON 字符串，避免 f-string 格式化错误
    identities_json = json.dumps(explicit_data.get('identities', []))
    explicit_topics_json = json.dumps(explicit_data.get('explicit_topics', []))
    politics_topics_json = json.dumps(explicit_data.get('politics_topics', []))
    interest_themes_json = json.dumps(portrait_data['interest_themes'])
    hidden_needs_json = json.dumps(portrait_data['hidden_needs'])
    user_tags_json = json.dumps(portrait_data['user_tags'])
    sentiment_score = portrait_data['sentiment_score']
    logic_score = portrait_data['logic_score']
    practice_ability = portrait_data.get('practice_ability', logic_score)
    psychological_quality = portrait_data.get('psychological_quality', sentiment_score)
    emotional_state = portrait_data.get('emotional_state', sentiment_score)
    analysis_summary = portrait_data['analysis_summary']
    risk_prompt_block = build_risk_prompt_block(risk_assessment)
    
    return f"""
    你现在是思政教育系统的资深导师。
    
    【用户基本信息】
    - 身份：{user_identity}
    - 年龄段：{user_age_group}
    - 专业：{user_major}
    
    【用户显性特征】（从用户表述中直接提取）
    - 身份：{identities_json}
    - 关注话题：{explicit_topics_json}
    - 政治话题：{politics_topics_json}
    
    【用户画像分析结果】（已通过深度分析得到）
    - 理想信念强度：{sentiment_score}/100
    - 逻辑思维能力：{logic_score}/100
    - 实践能力：{practice_ability}/100
    - 心理素质：{psychological_quality}/100
    - 情感状态：{emotional_state}/100
    - 兴趣主题：{interest_themes_json}
    - 隐性需求：{hidden_needs_json}
    - 用户标签：{user_tags_json}
    - 画像分析：{analysis_summary}
    - 用户提问风险分析：{risk_prompt_block}
    
    基于上述用户画像分析结果，请为该用户提供个性化、深度且富有指导意义的回复。
    你的回复应该：
    1. 准确把握用户的情感状态和需求
    2. 根据用户的兴趣主题和隐性需求进行有针对性的引导
    3. 结合用户的理想信念强度和逻辑思维能力进行表达，但不要直接提及这些分数
    4. 提供有建设性的建议或思想指导
    5. 如果检测到风险信号，应适当鼓励，避免批评、贴标签或直接否定用户，优先帮助用户恢复节奏与信心
    6. 如果检测到较高风险信号，应优先采取稳妥、安全、支持性的回应方式
    7. 如果当前提问适合使用案例来说明问题，请优先给出一个贴近用户问题的正面案例和一个反面案例，帮助用户理解“什么做法值得参考、什么做法需要避免”
    8. 案例必须紧扣用户当前提问，可以是简短、概括化的情境示例，不要虚构具体机构、具体人物或明显不真实的细节
    9. 如果当前提问本身不适合举正反面案例，就不要强行加入案例，直接给出自然、具体的分析和建议
    10. 可以使用适度 Markdown 提升可读性，例如标题、列表、加粗和代码块，但不要过度排版
    
    请输出有温度、有深度的导师回复（不需要JSON格式，直接返回回复文本）。
    """


def generate_personalized_response(
    user_text: str,
    portrait_data: Dict[str, Any],
    user_identity: str,
    user_age_group: str,
    user_major: str = "未设置",
    explicit_data: Optional[Dict[str, List[str]]] = None,
    risk_assessment: Optional[Dict[str, Any]] = None
) -> str:
    """
    第二次调用大模型：基于完善的用户画像，生成个性化的回答
    输入：用户文本、NLP提取的显性特征、补全后的用户画像、用户基本信息
    输出：个性化的导师回复
    """
    if explicit_data is None:
        explicit_data = {"identities": [], "explicit_topics": [], "politics_topics": []}

    system_prompt_stage2 = build_personalized_system_prompt(
        portrait_data=portrait_data,
        user_identity=user_identity,
        user_age_group=user_age_group,
        user_major=user_major,
        explicit_data=explicit_data,
        risk_assessment=risk_assessment
    )
    
    # 第二次调用大模型
    logger.info("第二阶段：调用大模型生成个性化回答...")
    response2 = dashscope.Generation.call(
        model=dashscope.Generation.Models.qwen_turbo,
        messages=[  # type: ignore
            {"role": "system", "content": system_prompt_stage2},
            {"role": "user", "content": user_text}
        ],
        result_format="message"
    )
    
    if response2.status_code != HTTPStatus.OK:  # type: ignore
        raise Exception("第二阶段大模型API调用失败")
    
    reply_text = sanitize_ai_text(response2.output.choices[0]["message"]["content"])  # type: ignore
    logger.info("第二阶段完成，生成回复")
    # 将第二阶段模型生成的原始回复打印到终端，方便调试与观察
    try:
        print("\n=== 第二阶段原始回复 ===\n" + reply_text + "\n====================\n")
    except Exception:
        # 打印失败时仍确保日志记录
        logger.info("无法将第二阶段回复打印到终端，可能包含非文本内容")

    logger.info(f"第二阶段原始回复: {reply_text!r}")

    return reply_text


def generate_response_with_deepseek(
    user_text: str,
    portrait_data: Dict[str, Any],
    user_identity: str,
    user_age_group: str,
    user_major: str = "未设置",
    explicit_data: Optional[Dict[str, List[str]]] = None,
    risk_assessment: Optional[Dict[str, Any]] = None
) -> str:
    """
    使用 DeepSeek 大模型生成个性化回答（使用 OpenAI 兼容接口）
    """
    if explicit_data is None:
        explicit_data = {"identities": [], "explicit_topics": [], "politics_topics": []}

    system_prompt = build_personalized_system_prompt(
        portrait_data=portrait_data,
        user_identity=user_identity,
        user_age_group=user_age_group,
        user_major=user_major,
        explicit_data=explicit_data,
        risk_assessment=risk_assessment
    )
    
    try:
        logger.info("调用 DeepSeek 大模型生成回答...")
        
        # 使用 OpenAI 兼容接口调用 DeepSeek
        response = deepseek_client.chat.completions.create(
            model=DEEPSEEK_MODEL_ID,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text}
            ],
            temperature=0.7,
            max_tokens=2048,
            stream=False  # 不使用流式输出
        )
        
        # 提取返回的内容
        reply_text = response.choices[0].message.content or ""
        logger.info("DeepSeek 大模型回答生成完成")
        
        try:
            if reply_text:
                print("\n=== DeepSeek 大模型回复 ===\n" + reply_text + "\n====================\n")
        except Exception:
            logger.info("无法将 DeepSeek 回复打印到终端")

        return sanitize_ai_text(reply_text)
    
    except Exception as e:
        logger.error(f"DeepSeek 大模型调用失败: {str(e)}")
        raise Exception(f"DeepSeek 大模型调用失败: {str(e)}")


def generate_response_with_kimi(
    user_text: str,
    portrait_data: Dict[str, Any],
    user_identity: str,
    user_age_group: str,
    user_major: str = "未设置",
    explicit_data: Optional[Dict[str, List[str]]] = None,
    risk_assessment: Optional[Dict[str, Any]] = None
) -> str:
    """
    使用 Kimi 大模型生成个性化回答（使用 OpenAI 兼容接口）
    """
    if explicit_data is None:
        explicit_data = {"identities": [], "explicit_topics": [], "politics_topics": []}

    system_prompt = build_personalized_system_prompt(
        portrait_data=portrait_data,
        user_identity=user_identity,
        user_age_group=user_age_group,
        user_major=user_major,
        explicit_data=explicit_data,
        risk_assessment=risk_assessment
    )

    try:
        logger.info("调用 Kimi 大模型生成回答...")

        # 使用 OpenAI 兼容接口调用 Kimi
        response = kimi_client.chat.completions.create(
            model=KIMI_MODEL_ID,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text}
            ],
            temperature=0.7,
            max_tokens=2048,
            stream=False  # 不使用流式输出
        )

        # 提取返回的内容
        reply_text = response.choices[0].message.content or ""
        logger.info("Kimi 大模型回答生成完成")

        try:
            if reply_text:
                print("\n=== Kimi 大模型回复 ===\n" + reply_text + "\n====================\n")
        except Exception:
            logger.info("无法将 Kimi 回复打印到终端")

        return sanitize_ai_text(reply_text)

    except Exception as e:
        logger.error(f"Kimi 大模型调用失败: {str(e)}")
        raise Exception(f"Kimi 大模型调用失败: {str(e)}")


def generate_responses_dual_models(
    user_text: str,
    portrait_data: Dict[str, Any],
    user_identity: str,
    user_age_group: str,
    user_major: str = "未设置",
    explicit_data: Optional[Dict[str, List[str]]] = None,
    risk_assessment: Optional[Dict[str, Any]] = None
) -> Dict[str, str]:
    """
    并行调用 Qwen、DeepSeek 和 Kimi 大模型生成回答
    返回三个模型的各自回复
    """
    if explicit_data is None:
        explicit_data = {"identities": [], "explicit_topics": [], "politics_topics": []}

    replies = {}
    errors = {}
    
    # 使用线程池并行调用三个模型
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        future_qwen = executor.submit(
            generate_personalized_response,
            user_text,
            portrait_data,
            user_identity,
            user_age_group,
            user_major,
            explicit_data,
            risk_assessment
        )
        
        future_deepseek = executor.submit(
            generate_response_with_deepseek,
            user_text,
            portrait_data,
            user_identity,
            user_age_group,
            user_major,
            explicit_data,
            risk_assessment
        )

        future_kimi = executor.submit(
            generate_response_with_kimi,
            user_text,
            portrait_data,
            user_identity,
            user_age_group,
            user_major,
            explicit_data,
            risk_assessment
        )
        
        # 获取 Qwen 的结果
        try:
            replies["qwen"] = future_qwen.result(timeout=60)
            logger.info("Qwen 大模型回答获取成功")
        except Exception as e:
            logger.error(f"Qwen 大模型回答获取失败: {str(e)}")
            errors["qwen"] = str(e)
        
        # 获取 DeepSeek 的结果
        try:
            replies["deepseek"] = future_deepseek.result(timeout=60)
            logger.info("DeepSeek 大模型回答获取成功")
        except Exception as e:
            logger.error(f"DeepSeek 大模型回答获取失败: {str(e)}")
            errors["deepseek"] = str(e)

        # 获取 Kimi 的结果
        try:
            replies["kimi"] = future_kimi.result(timeout=60)
            logger.info("Kimi 大模型回答获取成功")
        except Exception as e:
            logger.error(f"Kimi 大模型回答获取失败: {str(e)}")
            errors["kimi"] = str(e)
    
    # 检查是否至少有一个模型成功
    if not replies:
        logger.error(f"三个模型都失败了: {errors}")
        raise Exception(
            "三个大模型调用都失败: "
            f"Qwen={errors.get('qwen')}, DeepSeek={errors.get('deepseek')}, Kimi={errors.get('kimi')}"
        )
    
    # 为失败的模型设置空字符串（后续评分时会给0分）
    if "qwen" not in replies:
        replies["qwen"] = ""
        logger.warning("Qwen 生成失败，将评分设为0")
    if "deepseek" not in replies:
        replies["deepseek"] = ""
        logger.warning("DeepSeek 生成失败，将评分设为0")
    if "kimi" not in replies:
        replies["kimi"] = ""
        logger.warning("Kimi 生成失败，将评分设为0")
    
    return replies


def _extract_json(text: str) -> Dict[str, Any]:
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise ValueError("未找到JSON内容")
    return json.loads(match.group(0))


SCORE_DIMENSIONS = [
    "理论贯彻度",
    "主流意识形态弘扬",
    "政治立场引导",
    "社会主义核心价值观传播",
    "品德与人格塑造",
    "理想信念培育",
    "社会发展适配",
    "热点融入度",
    "学生需求契合",
    "个性与专业适配",
    "成长增量体现",
]


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return default


def score_ai_response(user_text: str, reply_text: str, portrait_data: Dict[str, Any], rag_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    额外调用大模型对回复评分，返回分数与改进意见
    """
    portrait_json = json.dumps(portrait_data, ensure_ascii=False)

    # 如果提供了 RAG 信息，将其摘要加入评分提示，以便评分模型考虑与权威库的一致性
    rag_summary = ""
    if rag_info:
        try:
            if not rag_info.get("available", True):
                rag_summary = f"RAG不可用: {rag_info.get('reason', '')}\n"
            else:
                # rag_info 可能直接包含 distances/max_distance/difference_flag 或包含在 result 中，兼容两种格式
                result_data = rag_info.get("result")
                res = result_data if isinstance(result_data, dict) else rag_info
                diff_flag = bool(res.get("difference_flag", False) or (res.get("consistent") is False))
                max_distance = res.get("max_distance") or res.get("distance")
                # 提炼证据摘要（若存在）
                evidence = res.get("evidence") or rag_info.get("evidence")
                evidence_snippet = "" if not evidence else (evidence[0][:200] + "...")
                rag_summary = (
                    f"RAG审查可用: True\n差异显著: {diff_flag}\n最大距离: {max_distance}\n证据片段: {evidence_snippet}\n"
                )
        except Exception:
            rag_summary = "RAG审查信息不可用\n"

    system_prompt_score = f"""
    你是一个严格的回复质量评估器。请根据用户画像、用户问题与AI回复进行评分。
    用户画像：{portrait_json}
    {rag_summary}
    评分范围 0-100。若分数低于80，请给出可执行的改进意见；若>=80，可给出简短肯定。
    评分标准如下，请严格按评分标准给分：
    理论贯彻度
        10分：完全贯彻马克思主义理论及中国化成果；
        8分：核心理论无偏差，细节待完善；
        6分：部分契合，非原则性疏漏；
        <6分：存在意识形态风险
    主流意识形态弘扬	
        10分：坚定弘扬国家主流意识形态，无模糊表述；
        8分：弘扬方向正确，力度不足；
        6分：提及但无实质内容；
        <6分：与主流意识形态冲突
    政治立场引导	
        10分：明确引导正确政治立场、价值观；
        8分：立场清晰，引导性一般；
        6分：立场不鲜明；
        <6分：立场有偏差
    社会主义核心价值观传播	
        10分：深度融入，有鲜活载体；
        8分：有体现，载体不够典型；
        6分：提及但流于形式；
        <6分：无相关元素
    品德与人格塑造	
        10分：有效提升道德修养、塑造健全人格；
        8分：有引导作用，效果一般；
        6分：内容空洞；
        <6分：无品德教育元素
    理想信念培育	
        10分：强化理想信念，精神引领明确；
        8分：提及理想信念，引领力不足；
        6分：内容流于表面；
        <6分：无相关内容
    社会发展适配	
        10分：及时反映社会新变化、新时代要求；
        8分：适配核心变化，关联不紧密；
        6分：提及变化，滞后性明显；
        <6分：内容严重过时
    热点融入度	
        10分：融入近1年社会热点，贴合现实；
        8分：融入热点，结合不够自然；
        6分：热点提及滞后；
        <6分：无新时代热点元素
    学生需求契合	
        10分：精准解决思想困惑、实际问题；
        8分：契合核心需求，方案不细化；
        6分：部分契合，针对性弱；
        <6分：与需求无关
    个性与专业适配	
        10分：适配不同年级/专业画像，差异化设计；
        8分：有初步差异化，适配度一般；
        6分：无明显差异化；
        <6分：“千人一面”
    成长增量体现	
        10分：显著提升理论素养、实践能力等；
        8分：有明确增量，幅度一般；
        6分：增量不明显；
        <6分：无实质增量

        必须严格返回 JSON，不包含其他内容，格式如下：
        {{
            "score": 0-100,
            "feedback": "...",
            "dimension_scores": {{
                "理论贯彻度": 0-10,
                "主流意识形态弘扬": 0-10,
                "政治立场引导": 0-10,
                "社会主义核心价值观传播": 0-10,
                "品德与人格塑造": 0-10,
                "理想信念培育": 0-10,
                "社会发展适配": 0-10,
                "热点融入度": 0-10,
                "学生需求契合": 0-10,
                "个性与专业适配": 0-10,
                "成长增量体现": 0-10
            }}
        }}
    """

    response = dashscope.Generation.call(
        model=dashscope.Generation.Models.qwen_max,
        messages=[  # type: ignore
            {"role": "system", "content": system_prompt_score},
            {"role": "user", "content": f"用户问题：{user_text}\n\nAI回复：{reply_text}"}
        ],
        result_format="message"
    )

    if response.status_code != HTTPStatus.OK:  # type: ignore
        raise Exception("回复评分大模型API调用失败")

    raw = response.output.choices[0]["message"]["content"]  # type: ignore
    logger.info(f"第四次调用评分原始输出: {raw!r}")

    try:
        score_data = json.loads(raw)
    except Exception:
        score_data = _extract_json(raw)

    total_score = max(0, min(100, _safe_int(score_data.get("score", 0), 0)))
    feedback = str(score_data.get("feedback", "")).strip()

    raw_dimension_scores = score_data.get("dimension_scores", {})
    if not isinstance(raw_dimension_scores, dict):
        raw_dimension_scores = {}

    normalized_dimension_scores: Dict[str, int] = {}
    for dimension in SCORE_DIMENSIONS:
        value = raw_dimension_scores.get(dimension)
        if value is None:
            for k, v in raw_dimension_scores.items():
                if str(k).strip() == dimension:
                    value = v
                    break
        normalized_dimension_scores[dimension] = max(0, min(10, _safe_int(value, 0)))

    result = {
        "score": total_score,
        "feedback": feedback,
        "dimension_scores": normalized_dimension_scores,
    }
    logger.info(
        "第四次调用评分结果: "
        f"score={result['score']}, feedback={result['feedback']!r}, "
        f"dimension_scores={result['dimension_scores']}"
    )
    return result


# 全局ChromaDB客户端和Collection缓存（避免重复初始化）
_CHROMADB_CLIENT = None
_CHROMADB_COLLECTION = None

def _get_chromadb_collection():
    """获取ChromaDB的collection，使用缓存避免重复初始化"""
    global _CHROMADB_CLIENT, _CHROMADB_COLLECTION
    
    if _CHROMADB_COLLECTION is not None:
        return _CHROMADB_COLLECTION
    
    try:
        import chromadb
        
        if _CHROMADB_CLIENT is None:
            try:
                _CHROMADB_CLIENT = chromadb.PersistentClient(path="./my_sizheng_db")
            except Exception:
                _CHROMADB_CLIENT = chromadb.Client()
        
        if hasattr(_CHROMADB_CLIENT, 'get_or_create_collection'):
            _CHROMADB_COLLECTION = _CHROMADB_CLIENT.get_or_create_collection(name='political_education_v1')
        elif hasattr(_CHROMADB_CLIENT, 'get_collection'):
            try:
                _CHROMADB_COLLECTION = _CHROMADB_CLIENT.get_collection(name='political_education_v1')
            except Exception:
                pass
        
        return _CHROMADB_COLLECTION
    except Exception as e:
        logger.warning(f"获取ChromaDB collection失败: {e}")
        return None

def rag_review_reply(reply_text: str, user_text: str, k: int = 3) -> Dict[str, Any]:
    """
    使用向量数据库检索与 `reply_text` 相关的文档，计算与检索到文档的向量距离（余弦距离）。
    返回格式示例：
    {
      "available": True/False,
      "distances": [0.12, 0.45],
      "max_distance": 0.45,
      "difference_flag": True/False,  # 当任一 distance > 0.8
      "evidence": ["doc1 text", ...]
    }
    """
    try:
        import numpy as _np
    except Exception as e:
        logger.info(f"RAG依赖缺失: {e}")
        return {"available": False, "reason": f"依赖缺失: {e}"}

    # 检查全局embedding模型
    if EMBEDDING_MODEL is None:
        return {"available": False, "reason": "Embedding模型未加载"}

    try:
        # 获取collection（使用缓存）
        coll = _get_chromadb_collection()
        if coll is None:
            return {"available": False, "reason": "向量库 collection 未找到"}

        # 编码回答文本
        q_emb = EMBEDDING_MODEL.encode(reply_text, convert_to_numpy=True)

        # 检索 top-k 文档（兼容不同 chromadb 接口）
        try:
            res = coll.query(query_embeddings=[q_emb.tolist()], n_results=k, include=['documents'])
            docs = []
            if isinstance(res, dict) and 'documents' in res and res['documents'] is not None:
                for dl in res['documents']:
                    if isinstance(dl, list):
                        docs.extend(dl)
            elif isinstance(res, list):
                docs = res
        except Exception:
            try:
                res = coll.query(q_emb, n_results=k)
                docs = res if isinstance(res, list) else []
            except Exception:
                docs = []

        if not docs:
            return {"available": True, "distances": [], "max_distance": None, "difference_flag": False, "evidence": []}

        # 批量编码文档
        doc_embs = EMBEDDING_MODEL.encode(docs, convert_to_numpy=True)
        if doc_embs.ndim == 1:
            doc_embs = doc_embs.reshape(1, -1)

        # 计算余弦距离
        q_norm = _np.linalg.norm(q_emb)
        doc_norms = _np.linalg.norm(doc_embs, axis=1)
        sims = (_np.dot(doc_embs, q_emb) / (doc_norms * q_norm + 1e-12)).tolist()
        distances = [1.0 - float(s) for s in sims]
        max_distance = max(distances)
        difference_flag = any(d > 0.8 for d in distances)

        return {
            "available": True,
            "distances": distances,
            "max_distance": float(max_distance),
            "difference_flag": bool(difference_flag),
            "evidence": docs
        }

    except Exception as e:
        logger.exception("RAG 审查内部错误")
        return {"available": False, "reason": str(e)}



def regenerate_response_with_feedback(
    user_text: str,
    reply_text: str,
    feedback: str,
    portrait_data: Dict[str, Any],
    user_identity: str,
    user_age_group: str,
    user_major: str,
    explicit_data: Dict[str, List[str]]
) -> str:
    """
    若评分低于阈值，根据改进意见重写回答
    """
    system_prompt_stage2 = build_personalized_system_prompt(
        portrait_data=portrait_data,
        user_identity=user_identity,
        user_age_group=user_age_group,
        user_major=user_major,
        explicit_data=explicit_data
    )

    user_prompt = (
        "请根据以下改进意见重写回复，保持友好、清晰、有针对性。\n\n"
        f"原回复：{reply_text}\n\n"
        f"改进意见：{feedback}\n\n"
        "请直接输出改写后的最终回复文本。"
    )

    response = dashscope.Generation.call(
        model=dashscope.Generation.Models.qwen_max,
        messages=[  # type: ignore
            {"role": "system", "content": system_prompt_stage2},
            {"role": "user", "content": user_text},
            {"role": "user", "content": user_prompt}
        ],
        result_format="message"
    )

    if response.status_code != HTTPStatus.OK:  # type: ignore
        raise Exception("重写回复大模型API调用失败")

    return sanitize_ai_text(response.output.choices[0]["message"]["content"])  # type: ignore

# ======================== 第三阶段：标签整合优化 ========================

def consolidate_user_tags(all_tags: List[str], all_hidden_needs: List[str]) -> Dict[str, List[str]]:
    """
    第三次调用大模型：整合和优化用户标签与隐性需求
    输入：所有去重后的标签和隐性需求
    输出：整合后的标签和隐性需求
    """
    
    # 预处理 JSON 字符串，避免 f-string 格式化错误
    all_tags_json = json.dumps(all_tags)
    all_hidden_needs_json = json.dumps(all_hidden_needs)
    
    # 构造第三阶段的系统提示词
    system_prompt_stage3 = f"""
    你现在是思政教育系统的标签管理专家。
    
    【任务】：对以下用户标签和隐性需求进行整合优化
    
    当前标签列表：{all_tags_json}
    当前隐性需求：{all_hidden_needs_json}
    
    请执行以下操作：
    1. 去除完全重复的标签和需求
    2. 合并含义相同或相似的标签（如"学生"和"大学生"应该合并为一个）
    3. 保留最能代表用户特征的标签（不超过15个）
    4. 同样处理隐性需求，保留最核心的需求（不超过5个）
    5. 确保标签更加简洁、规范、易于理解
    
    必须严格返回 JSON 格式：
    {{
      "consolidated_tags": ["标签1", "标签2", ...],
      "consolidated_needs": ["需求1", "需求2", ...]
    }}
    """
    
    # 第三次调用大模型
    logger.info("第三阶段：调用大模型进行标签整合...")
    response3 = dashscope.Generation.call(
        model=dashscope.Generation.Models.qwen_turbo,
        messages=[  # type: ignore
            {"role": "system", "content": system_prompt_stage3},
            {"role": "user", "content": "请整合我的标签和需求"}
        ],
        result_format="message"
    )
    
    if response3.status_code != HTTPStatus.OK:  # type: ignore
        raise Exception("第三阶段大模型API调用失败")
    
    consolidated_data = json.loads(response3.output.choices[0]["message"]["content"])  # type: ignore
    logger.info(f"第三阶段完成，标签整合结果：{repr(consolidated_data)}")
    
    return {
        "tags": consolidated_data["consolidated_tags"],
        "hidden_needs": consolidated_data["consolidated_needs"]
    }

@app.post("/chat")
async def chat_endpoint(data: ChatRequest):
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        user_text = data.message
        conversation: Optional[Dict[str, Any]] = None
        
        # --- 步骤 1: 获取用户ID并查询历史画像 ---
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, identity, age_group FROM users WHERE username = %s", (data.username,))
            user_res = cursor.fetchone()
            if not user_res: 
                raise HTTPException(status_code=404, detail="User not found")
            
            uid = user_res["id"]  # type: ignore
            user_identity = user_res["identity"]  # type: ignore
            user_age_group = user_res["age_group"]  # type: ignore
            
            # 确保 uid 是整数类型
            uid = int(uid)  # type: ignore

            if data.conversation_id:
                conversation = get_conversation_for_user(conn, uid, int(data.conversation_id))
            else:
                conversation = create_conversation_for_user(conn, uid)
            
            # 获取用户专业信息
            cursor.execute("SELECT current_major FROM user_portraits WHERE user_id = %s ORDER BY id DESC LIMIT 1", (uid,))  # type: ignore
            major_res = cursor.fetchone()
            user_major = major_res["current_major"] if major_res else "计算机科学"  # type: ignore
            
            # 查询历史画像
            cursor.execute("SELECT ideal_belief, logic_thinking, practice_ability, psychological_quality, emotional_state, hidden_need, tags, current_major FROM user_portraits WHERE user_id = %s ORDER BY id DESC LIMIT 10", (uid,))  # type: ignore
            history_portraits = cursor.fetchall()
        
        # 整合历史画像
        historical_tags = set()
        historical_hidden_needs = set()
        for portrait in history_portraits:
            if portrait["tags"]:  # type: ignore
                historical_tags.update(portrait["tags"].split(","))  # type: ignore
            if portrait["hidden_need"]:  # type: ignore
                historical_hidden_needs.update(portrait["hidden_need"].split(","))  # type: ignore
        
        # --- 步骤 2: NLP 预处理提取显性特征 ---
        explicit_data = nlp_pre_processing(user_text)
        rule_based_needs = dynamic_semantic_completion(user_text)
        risk_assessment = assess_question_risk(user_text, explicit_data)
        logger.info(f"当前提问风险判定: {risk_assessment}")
        
        # 构造历史上下文
        historical_context = {
            "historical_tags": list(historical_tags),
            "historical_hidden_needs": list(historical_hidden_needs),
            "rule_based_needs": rule_based_needs  # 将规则判定的需求传给下游
        }
        
        # ============ 第一次调用大模型：用户画像补全与情感量化 ============
        portrait_data = enhance_user_portrait(
            user_text=user_text,
            user_identity=str(user_identity),
            user_age_group=str(user_age_group),
            historical_context=historical_context,
            explicit_data=explicit_data
        )
        
        # ============ 第二次调用大模型：基于完善画像生成个性化回答（双模型并行生成） ============
        # 并行调用 Qwen、DeepSeek 和 Kimi，获得三个回答
        dual_replies = generate_responses_dual_models(
            user_text=user_text,
            portrait_data=portrait_data,
            user_identity=str(user_identity),
            user_age_group=str(user_age_group),
            user_major=str(user_major),
            explicit_data=explicit_data,
            risk_assessment=risk_assessment
        )
        
        # 对三个回答分别进行评分
        qwen_reply = dual_replies.get("qwen", "")
        deepseek_reply = dual_replies.get("deepseek", "")
        kimi_reply = dual_replies.get("kimi", "")
        
        qwen_score_result = None
        deepseek_score_result = None
        kimi_score_result = None
        
        logger.info("开始对三个模型的回答进行评分...")
        
        # 并行执行三个模型的RAG审查
        def perform_rag_review(reply_text: str) -> Dict[str, Any]:
            try:
                return rag_review_reply(reply_text=reply_text, user_text=user_text)
            except Exception as e:
                logger.warning(f"RAG审查失败: {str(e)}")
                return {"available": False, "reason": str(e)}
        
        rag_results = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            # 并行执行三个RAG审查
            future_qwen_rag = executor.submit(perform_rag_review, qwen_reply) if qwen_reply else None
            future_deepseek_rag = executor.submit(perform_rag_review, deepseek_reply) if deepseek_reply else None
            future_kimi_rag = executor.submit(perform_rag_review, kimi_reply) if kimi_reply else None
            
            # 获取RAG结果
            if future_qwen_rag:
                rag_results["qwen"] = future_qwen_rag.result(timeout=30)
            if future_deepseek_rag:
                rag_results["deepseek"] = future_deepseek_rag.result(timeout=30)
            if future_kimi_rag:
                rag_results["kimi"] = future_kimi_rag.result(timeout=30)
        
        logger.info("三个模型的RAG审查完成")
        
        # 获取RAG结果或使用默认值
        qwen_rag_result = rag_results.get("qwen", {"available": False})
        deepseek_rag_result = rag_results.get("deepseek", {"available": False})
        kimi_rag_result = rag_results.get("kimi", {"available": False})
        
        # 对 Qwen 的回答评分
        if qwen_reply:
            try:
                logger.info(f"Qwen RAG审查完成: {qwen_rag_result.get('difference_flag', False)}")
                qwen_score_result = score_ai_response(
                    user_text=user_text,
                    reply_text=qwen_reply,
                    portrait_data=portrait_data,
                    rag_info=qwen_rag_result
                )
                logger.info(f"Qwen 回答评分: {qwen_score_result['score']}")
            except Exception as e:
                logger.error(f"Qwen 回答评分失败: {str(e)}")
                qwen_score_result = {"score": 0, "feedback": f"评分失败: {str(e)}"}
        else:
            qwen_score_result = {"score": 0, "feedback": "模型未生成回答"}
            logger.info("Qwen 未生成回答，评分: 0")
        
        # 对 DeepSeek 的回答评分
        if deepseek_reply:
            try:
                logger.info(f"DeepSeek RAG审查完成: {deepseek_rag_result.get('difference_flag', False)}")
                deepseek_score_result = score_ai_response(
                    user_text=user_text,
                    reply_text=deepseek_reply,
                    portrait_data=portrait_data,
                    rag_info=deepseek_rag_result
                )
                logger.info(f"DeepSeek 回答评分: {deepseek_score_result['score']}")
            except Exception as e:
                logger.error(f"DeepSeek 回答评分失败: {str(e)}")
                deepseek_score_result = {"score": 0, "feedback": f"评分失败: {str(e)}"}
        else:
            deepseek_score_result = {"score": 0, "feedback": "模型未生成回答"}
            logger.info("DeepSeek 未生成回答，评分: 0")

        # 对 Kimi 的回答评分
        if kimi_reply:
            try:
                logger.info(f"Kimi RAG审查完成: {kimi_rag_result.get('difference_flag', False)}")
                kimi_score_result = score_ai_response(
                    user_text=user_text,
                    reply_text=kimi_reply,
                    portrait_data=portrait_data,
                    rag_info=kimi_rag_result
                )
                logger.info(f"Kimi 回答评分: {kimi_score_result['score']}")
            except Exception as e:
                logger.error(f"Kimi 回答评分失败: {str(e)}")
                kimi_score_result = {"score": 0, "feedback": f"评分失败: {str(e)}"}
        else:
            kimi_score_result = {"score": 0, "feedback": "模型未生成回答"}
            logger.info("Kimi 未生成回答，评分: 0")
        
        # 比较评分，选择分数更高的回答
        qwen_final_score = qwen_score_result.get("score", 0) if qwen_score_result else 0
        deepseek_final_score = deepseek_score_result.get("score", 0) if deepseek_score_result else 0
        kimi_final_score = kimi_score_result.get("score", 0) if kimi_score_result else 0

        score_map = {
            "Qwen": qwen_final_score,
            "DeepSeek": deepseek_final_score,
            "Kimi": kimi_final_score
        }
        model_order = ["Qwen", "DeepSeek", "Kimi"]
        best_score = max(score_map.values())
        selected_model = next(model for model in model_order if score_map[model] == best_score)
        
        if selected_model == "Qwen":
            reply_text = qwen_reply
            review_result = qwen_score_result
        elif selected_model == "DeepSeek":
            reply_text = deepseek_reply
            review_result = deepseek_score_result
        else:
            reply_text = kimi_reply
            review_result = kimi_score_result

        logger.info(
            "选择的模型: "
            f"{selected_model} (Qwen: {qwen_final_score}, DeepSeek: {deepseek_final_score}, Kimi: {kimi_final_score})"
        )
        
        # --- 步骤 3: 构建多维度标签体系（整合结果）---
        portrait_tags = {
            "demographic": explicit_data["identities"],
            "behavior_preference": portrait_data["interest_themes"],
            "emotional_need": portrait_data["hidden_needs"]
        }
        
        # 去重整合历史和当前标签
        all_demographic = list(set(explicit_data["identities"]) | historical_tags)
        all_behavior = list(set(portrait_data["interest_themes"]) | historical_tags)
        all_emotional = list(set(portrait_data["hidden_needs"]) | historical_hidden_needs)
        
        portrait_tags_final = {
            "demographic": all_demographic,
            "behavior_preference": all_behavior,
            "emotional_need": all_emotional
        }
        
        # --- 步骤 4: 数据库持久化 ---
        with conn.cursor() as cursor:
            # 对所有标签进行去重
            all_tags_list = portrait_tags_final["demographic"] + portrait_tags_final["behavior_preference"] + portrait_tags_final["emotional_need"]
            all_tags_deduplicated = list(dict.fromkeys(all_tags_list))  # 保持顺序的去重
            
            # 隐性需求也要去重
            all_hidden_needs = portrait_data["hidden_needs"] + list(historical_hidden_needs)
            all_hidden_needs_deduplicated = list(dict.fromkeys(all_hidden_needs))  # 保持顺序的去重
            
            # ============ 第三次调用大模型：标签整合与优化 ============
            consolidated_result = consolidate_user_tags(all_tags_deduplicated, all_hidden_needs_deduplicated)
            
            # 使用整合后的标签和需求
            all_tags_str = ",".join(consolidated_result["tags"][:20])  # 只存储前20个标签
            hidden_need_str = ",".join(consolidated_result["hidden_needs"])[:500]
            
            # 检查是否已有画像记录
            cursor.execute("SELECT id FROM user_portraits WHERE user_id = %s ORDER BY id DESC LIMIT 1", (uid,))  # type: ignore
            existing = cursor.fetchone()
            
            if existing:
                # 更新现有记录
                update_sql = """
                UPDATE user_portraits 
                SET ideal_belief = %s, logic_thinking = %s, practice_ability = %s, psychological_quality = %s, emotional_state = %s, hidden_need = %s, tags = %s, chat_content = %s 
                WHERE id = %s
                """
                cursor.execute(update_sql, (  # type: ignore
                    portrait_data["sentiment_score"],
                    portrait_data["logic_score"],
                    portrait_data.get("practice_ability", 70),
                    portrait_data.get("psychological_quality", 75),
                    portrait_data.get("emotional_state", 70),
                    hidden_need_str,
                    all_tags_str,
                    user_text,
                    existing["id"]  # type: ignore
                ))
            else:
                # 插入新记录
                insert_sql = """
                INSERT INTO user_portraits 
                (user_id, ideal_belief, logic_thinking, practice_ability, psychological_quality, emotional_state, hidden_need, tags, current_major, chat_content) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(insert_sql, (  # type: ignore
                    uid,
                    portrait_data["sentiment_score"],
                    portrait_data["logic_score"],
                    portrait_data.get("practice_ability", 70),
                    portrait_data.get("psychological_quality", 75),
                    portrait_data.get("emotional_state", 70),
                    hidden_need_str,
                    all_tags_str,
                    user_major,
                    user_text
                ))
            conn.commit()

        # --- 步骤 5: 保存聊天记录到 chat_history 表 ---
        chat_record_id = None  # 初始化，在保存失败时使用None
        try:
            with conn.cursor() as cursor:
                insert_chat_sql = """
                INSERT INTO chat_history 
                (user_id, conversation_id, user_message, user_emotion_score, user_ideal_belief, 
                 user_logic_thinking, user_practice_ability, user_psychological_quality,
                 user_hidden_needs, user_interest_themes, ai_reply, ai_reply_score, 
                 ai_reply_feedback, selected_model, qwen_score, deepseek_score, kimi_score) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                
                # 准备参数，确保类型正确
                hidden_needs_str = ",".join(portrait_data.get("hidden_needs", []))
                interest_themes_str = ",".join(portrait_data.get("interest_themes", []))
                emotion_score = portrait_data.get("emotional_state", 70)
                ideal_belief = portrait_data.get("sentiment_score", 80)
                logic_thinking = portrait_data.get("logic_score", 80)
                practice_ability = portrait_data.get("practice_ability", 70)
                psychological_quality = portrait_data.get("psychological_quality", 75)
                ai_score = review_result.get("score", 0) if review_result else 0
                ai_feedback = review_result.get("feedback", "") if review_result else ""
                
                logger.info(f"准备保存聊天记录 - user_id={uid}, score={ai_score}")
                
                cursor.execute(insert_chat_sql, (  # type: ignore
                    uid,  # user_id
                    conversation["id"] if conversation else None,  # conversation_id
                    user_text,  # user_message
                    emotion_score,  # user_emotion_score
                    ideal_belief,  # user_ideal_belief
                    logic_thinking,  # user_logic_thinking
                    practice_ability,  # user_practice_ability
                    psychological_quality,  # user_psychological_quality
                    hidden_needs_str,  # user_hidden_needs
                    interest_themes_str,  # user_interest_themes
                    reply_text,  # ai_reply
                    ai_score,  # ai_reply_score
                    ai_feedback,  # ai_reply_feedback
                    selected_model,  # selected_model
                    qwen_final_score,  # qwen_score
                    deepseek_final_score,  # deepseek_score
                    kimi_final_score  # kimi_score
                ))

                updated_conversation_title = conversation.get("title") if conversation else "新对话"
                if conversation and updated_conversation_title == "新对话":
                    updated_conversation_title = generate_conversation_title(user_text)
                    cursor.execute(
                        "UPDATE chat_conversations SET title = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                        (updated_conversation_title, conversation["id"])
                    )
                elif conversation:
                    cursor.execute(
                        "UPDATE chat_conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                        (conversation["id"],)
                    )

                conn.commit()
                chat_record_id = cursor.lastrowid
                if conversation:
                    conversation["title"] = updated_conversation_title
                logger.info(f"✅ 聊天记录已保存成功，chat_id={chat_record_id}")
        except Exception as save_err:
            logger.error(f"❌ 保存聊天记录失败: {str(save_err)}")
            logger.error(f"错误类型: {type(save_err).__name__}")
            # 不中断主流程，聊天记录保存失败不影响返回结果

        # --- 步骤 6: 返回封装结果 ---
        return {
            "status": "success",
            "reply": reply_text,
            "chat_id": chat_record_id,  # 新增：返回保存的聊天记录ID
            "conversation_id": conversation["id"] if conversation else None,
            "conversation": serialize_conversation(conversation) if conversation else None,
            "selected_model": selected_model,  # 新增：选择的模型
            "model_comparison": {  # 新增：两个模型的对比信息
                "qwen": {
                    "score": qwen_final_score,
                    "feedback": qwen_score_result.get("feedback", "") if qwen_score_result else "",
                    "dimension_scores": qwen_score_result.get("dimension_scores", {}) if qwen_score_result else {}
                },
                "deepseek": {
                    "score": deepseek_final_score,
                    "feedback": deepseek_score_result.get("feedback", "") if deepseek_score_result else "",
                    "dimension_scores": deepseek_score_result.get("dimension_scores", {}) if deepseek_score_result else {}
                },
                "kimi": {
                    "score": kimi_final_score,
                    "feedback": kimi_score_result.get("feedback", "") if kimi_score_result else "",
                    "dimension_scores": kimi_score_result.get("dimension_scores", {}) if kimi_score_result else {}
                }
            },
            "portrait_analysis": {
                "scores": {
                    "ideal_belief": portrait_data["sentiment_score"],
                    "logic_thinking": portrait_data["logic_score"],
                    "practice_ability": portrait_data.get("practice_ability", portrait_data["logic_score"]),
                    "psychological_quality": portrait_data.get("psychological_quality", portrait_data["sentiment_score"]),
                    "emotional_state": portrait_data.get("emotional_state", portrait_data["sentiment_score"])
                },
                "interest_themes": portrait_data["interest_themes"],
                "hidden_needs": portrait_data["hidden_needs"],
                "analysis_summary": portrait_data["analysis_summary"],
                "risk_assessment": risk_assessment,
                "dimensions": portrait_tags_final,
                "consolidated_tags": consolidated_result["tags"],
                "consolidated_needs": consolidated_result["hidden_needs"],
                "model_calls": {
                    "stage1": "用户画像补全与情感量化",
                    "stage2": "个性化回答生成（双模型并行）",
                    "stage3": "标签整合与优化",
                    "stage4": "回复评分与模型对比"
                },
                "review": {
                    "score": review_result["score"] if review_result else 0,
                    "feedback": review_result["feedback"] if review_result else "",
                    "dimension_scores": review_result.get("dimension_scores", {}) if review_result else {},
                    "passed": review_result["score"] >= 70 if review_result else False
                }
            }
        }

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.exception("Error in chat endpoint: %s", str(e))
        logger.error("Full traceback:\n%s", tb)
        return {"status": "error", "message": str(e)}
    finally:
        conn.close()


# ======================== 数据概览 API ========================
@app.get("/api/overview")
def get_overview(username: str):
    """
    获取系统数据统计概览
    包括：用户统计、问题统计、风险匹配、新闻、讨论话题、用户画像
    """
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # 仅允许管理员访问概览数据
            cursor.execute("SELECT identity, role FROM users WHERE username = %s", (username,))
            user_row = cursor.fetchone()
            if not user_row:
                raise HTTPException(status_code=404, detail="用户不存在")

            db_identity = str(cast(Any, user_row)["identity"] or "")
            db_role = normalize_db_role(cast(Optional[str], cast(Any, user_row)["role"]), db_identity)
            if db_role != "admin":
                raise HTTPException(status_code=403, detail="仅管理员可访问数据概览")

            # 1. 获取统计数据
            cursor.execute("SELECT COUNT(*) as count FROM users")
            row = cursor.fetchone()
            user_count = row["count"] if row else 0
            
            cursor.execute("SELECT COUNT(*) as count FROM chat_history")
            row = cursor.fetchone()
            question_count = row["count"] if row else 0
            
            # 讨论话题数
            topic_count = sum(len(cat.get("topics", [])) for cat in DISCUSSION_TOPIC_CATEGORIES)
            
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
            recent_questions = []
            for row in cursor.fetchall() or []:
                if row and row.get("user_message"):
                    msg = row["user_message"]
                    recent_questions.append({
                        "username": row.get("username", "Anonymous"),
                        "user_message": msg[:80] + "..." if len(msg) > 80 else msg,
                        "created_at": str(row["created_at"]) if row.get("created_at") else ""
                    })
            
            # 3. 获取风险匹配统计
            risk_mapping = []
            for rule in QUESTION_RISK_RULES:  # 显示全部风险类型
                risk_mapping.append({
                    "code": rule.get("code", ""),
                    "label": rule.get("label", ""),
                    "level": rule.get("level", "medium"),
                    "response_strategy": rule.get("response_strategy", "")[:50] + "..."
                })
            
            # 4. 实时爬取新闻标题
            try:
                news_data = fetch_daily_news(limit=6)
                news_titles = [
                    {
                        "title": news.get("title", ""),
                        "source": news.get("source", "未知来源")
                    }
                    for news in news_data if news.get("title")
                ]
                # 如果爬取失败，使用备选方案
                if not news_titles:
                    news_titles = [
                        {
                            "title": "人民网评：坚定不移推进中国式现代化",
                            "source": "人民网"
                        },
                        {
                            "title": "新时代的青年使命与担当",
                            "source": "新华网"
                        }
                    ]
            except Exception as e:
                logger.warning(f"爬取新闻失败: {str(e)}")
                news_titles = [
                    {
                        "title": "人民网评：坚定不移推进中国式现代化",
                        "source": "人民网"
                    },
                    {
                        "title": "新时代的青年使命与担当",
                        "source": "新华网"
                    }
                ]
            
            # 5. 获取讨论话题
            topics = []
            for category in DISCUSSION_TOPIC_CATEGORIES:
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
                if not row:
                    continue
                    
                hidden_needs = []
                if row.get("hidden_need"):
                    hidden_needs = [h.strip() for h in str(row["hidden_need"]).split(",") if h.strip()]
                
                tags = []
                if row.get("tags"):
                    tags = [t.strip() for t in str(row["tags"]).split(",") if t.strip()]
                
                users.append({
                    "username": row.get("username", "Anonymous"),
                    "identity": row.get("identity", "Unknown"),
                    "age_group": row.get("age_group", "Unknown"),
                    "major": row.get("current_major") or "未设置",
                    "portrait": {
                        "ideal": row.get("ideal_belief") or 80,
                        "logic": row.get("logic_thinking") or 80,
                        "practice": row.get("practice_ability") or 70,
                        "psychological": row.get("psychological_quality") or 75,
                        "emotion": row.get("emotional_state") or 70
                    },
                    "tags": tags[:5],
                    "hidden_needs": hidden_needs[:3]
                })
            
            # 返回概览数据
            return {
                "status": "success",
                "data": {
                    "stats": {
                        "user_count": user_count,
                        "question_count": question_count,
                        "news_count": len(news_titles),
                        "topic_count": topic_count,
                        "risk_category_count": len(QUESTION_RISK_RULES)
                    },
                    "recent_questions": recent_questions,
                    "risk_mapping": risk_mapping,
                    "news_titles": news_titles[:6],
                    "topics": topics,
                    "users": users
                }
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取数据概览失败: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)