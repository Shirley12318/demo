import json
import os
import re
import logging
from datetime import datetime
from html import unescape
from urllib.parse import urljoin, urlparse
import sqlite3

# ======================== Hugging Face 国内镜像配置 ========================
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
os.environ['HF_HOME'] = os.path.join(os.getcwd(), '.cache', 'huggingface')
os.environ['TRANSFORMERS_CACHE'] = os.path.join(os.getcwd(), '.cache', 'transformers')
os.environ['SENTENCE_TRANSFORMERS_HOME'] = os.path.join(os.getcwd(), '.cache', 'sentence_transformers')

import jieba.posseg as pseg
from typing import Dict, Any, List, Optional, cast
from http import HTTPStatus
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import dashscope
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
import requests
import concurrent.futures
from openai import OpenAI

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

# 使用 SQLite 数据库
DB_PATH = os.path.join(os.path.dirname(__file__), "data.db")

dashscope.api_key = "sk-d2df76fb2d91448f97dc3d6d7007169e"

# DeepSeek 大模型配置
DEEPSEEK_API_KEY = "sk-d6a467fa118048a8aed508f6de87ddfb"
DEEPSEEK_API_BASE = "https://api.deepseek.com"
DEEPSEEK_MODEL_ID = "deepseek-chat"
deepseek_client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_API_BASE)

# Kimi 大模型配置
KIMI_API_KEY = "sk-Yur62xHSg8AW7PZGK9hZvJLtXXoPUpuRNDoBq12OY0KMDi8V"
KIMI_API_BASE = "https://api.moonshot.cn/v1"
KIMI_MODEL_ID = "kimi-k2-turbo-preview"
kimi_client = OpenAI(api_key=KIMI_API_KEY, base_url=KIMI_API_BASE)

# BERT情感分析模型
try:
    BERT_MODEL_NAME = "uer/roberta-base-finetuned-jd-binary-chinese"
    bert_tokenizer = AutoTokenizer.from_pretrained(BERT_MODEL_NAME)
    bert_model = AutoModelForSequenceClassification.from_pretrained(BERT_MODEL_NAME)
    bert_model.eval()
    logger.info("BERT情感分析模型加载成功")
except Exception as e:
    logger.warning(f"BERT模型加载失败: {str(e)}")
    bert_tokenizer = None
    bert_model = None

# RAG向量化模型
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

# ======================== 常量（风险、新闻等，原样保留） ========================
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
            "红色故事我来讲", "我心中的英雄", "我爱我的祖国", "我与祖国共成长",
            "红色基因代代传", "强国有我", "青春心向党", "感恩社会报效祖国",
        ],
    },
    {
        "category": "青年使命与理想担当",
        "topics": [
            "争做新时代好青年", "新时代青年使命", "青年榜样力量", "乡村振兴青年有为",
            "理想与信念", "做有担当的新时代青年",
        ],
    },
    {
        "category": "品德修养与志愿服务",
        "topics": [
            "学雷锋，在行动", "诚信伴我成长", "践行社会主义核心价值观", "志愿服务与奉献", "廉洁修身诚信做人",
        ],
    },
    {
        "category": "文化自信与民族团结",
        "topics": [
            "传统文化我传承", "文化自信从我做起", "民族团结一家亲",
        ],
    },
    {
        "category": "劳动实践与绿色生活",
        "topics": [
            "劳动最光荣", "保护环境，从我做起", "节约小标兵", "低碳生活绿色发展",
        ],
    },
    {
        "category": "法治安全与网络文明",
        "topics": [
            "法治教育", "国家安全青年有责", "网络文明青年先行",
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
        "patterns": [r"不想学(习)?了?", r"学不下去", r"不想上课", r"不想写作业", r"厌学", r"摆烂", r"躺平", r"读不进去", r"一点都不想碰书", r"上课听不进去", r"完全没学习动力", r"不想复习", r"看到书就烦", r"卷不动了", r"学废了", r"真的不想卷了", r"学得我想逃"],
        "response_strategy": "先共情和鼓励，避免贴标签或责备；帮助用户拆解学习任务、恢复节奏感，并提供短期可执行的小目标。",
    },
    {
        "code": "exam_anxiety",
        "label": "考试焦虑明显",
        "level": "medium",
        "patterns": [r"考试.*紧张", r"一到考试.*慌", r"怕挂科", r"复习不完", r"考前焦虑", r"一考试就失眠", r"担心考砸", r"考试要完了", r"这次肯定挂了", r"一想到考试就慌", r"复习越看越慌"],
        "response_strategy": "先缓解考试焦虑，避免单纯施压；优先帮助用户做复习拆解、时间分配和情绪稳定，强调先完成关键部分。",
    },
    {
        "code": "procrastination_risk",
        "label": "拖延失控倾向",
        "level": "medium",
        "patterns": [r"总是拖到最后", r"一直拖延", r"拖着不想做", r"越拖越不想做", r"明知道要做却不做", r"拖延症", r"总想晚点再说", r"不到最后不动", r"一拖再拖", r"每次都卡在开始"],
        "response_strategy": "不要道德化评价拖延；帮助用户缩小任务颗粒度，先建立最小行动和外部约束，再逐步恢复执行感。",
    },
    {
        "code": "study_burnout",
        "label": "学习倦怠明显",
        "level": "medium",
        "patterns": [r"学什么都没感觉", r"越学越麻木", r"感觉学了也没用", r"对学习完全提不起兴趣", r"整个人对学习很麻木", r"已经学到没感觉了", r"学到恶心", r"脑子已经转不动了", r"越学越空", r"感觉自己快耗干了"],
        "response_strategy": "优先判断是否存在长期透支和倦怠，避免继续加压；帮助用户先恢复基本节律，再重新建立学习目标和成就反馈。",
    },
    {
        "code": "psychological_stress",
        "label": "心理压力明显",
        "level": "medium",
        "patterns": [r"压力好大", r"特别焦虑", r"快崩溃", r"撑不住", r"很疲惫", r"情绪很差", r"喘不过气", r"每天都好压抑", r"最近状态特别差", r"整个人很崩", r"心里堵得慌", r"绷不住了", r"破防了", r"emo了", r"心态炸了"],
        "response_strategy": "优先安抚情绪，避免空泛说教；提供减压和求助建议，必要时鼓励联系老师、辅导员或心理咨询资源。",
    },
    {
        "code": "sleep_disorder_risk",
        "label": "睡眠紊乱风险",
        "level": "medium",
        "patterns": [r"睡不着", r"失眠", r"晚上睡不着", r"半夜总醒", r"作息全乱了", r"白天没精神", r"凌晨还睡不着", r"越想越睡不着", r"天天熬到很晚", r"作息彻底废了", r"晚上根本停不下来"],
        "response_strategy": "先关注作息和情绪是否互相影响，避免只说“早点睡”；优先建议减少刺激、稳定睡前节律，并视情况建议寻求专业帮助。",
    },
    {
        "code": "interpersonal_withdrawal",
        "label": "人际退缩倾向",
        "level": "medium",
        "patterns": [r"不想跟任何人说话", r"不想社交", r"不想见人", r"跟室友相处不来", r"觉得自己融不进去", r"没有人理解我", r"不想和同学接触", r"只想一个人待着", r"谁都不想理", r"越来越不想开口"],
        "response_strategy": "先承认人际压力的真实感受，不强迫用户立刻外向；建议从低压力沟通、边界表达和可信任对象开始恢复联系。",
    },
    {
        "code": "social_comparison_anxiety",
        "label": "同辈比较焦虑",
        "level": "medium",
        "patterns": [r"别人都比我强", r"一比较就很难受", r"同学都比我厉害", r"感觉自己被甩开了", r"身边的人都在进步", r"我好像最差", r"越看别人越焦虑"],
        "response_strategy": "先降低用户被比较带来的挫败感，避免继续强化排名思维；帮助用户把注意力转回自身节奏、阶段目标和可控改进。",
    },
    {
        "code": "adaptation_difficulty",
        "label": "新环境适应困难",
        "level": "medium",
        "patterns": [r"不适应大学生活", r"刚来学校很不适应", r"换了环境很难受", r"适应不了现在的节奏", r"到新环境后状态很差", r"在学校总觉得别扭", r"新学期完全不在状态"],
        "response_strategy": "先承认适应期的不稳定是常见现象，避免要求用户立刻正常化；建议从作息、同伴联系和日常节奏三个方面逐步重建熟悉感。",
    },
    {
        "code": "campus_conflict",
        "label": "校园关系冲突",
        "level": "medium",
        "patterns": [r"和室友闹矛盾", r"和同学吵架", r"宿舍关系很差", r"室友让我很烦", r"班里关系很僵", r"同学故意针对我", r"在宿舍待不下去", r"室友阴阳我", r"班里有人故意找事", r"天天在宿舍受气"],
        "response_strategy": "避免煽动对立；先帮助用户区分情绪和事实，建议用低冲突表达、边界沟通和求助辅导员等方式降温处理。",
    },
    {
        "code": "bullying_or_exclusion_risk",
        "label": "疑似被排斥或欺凌",
        "level": "high",
        "patterns": [r"他们都孤立我", r"被排挤", r"被针对", r"被欺负", r"总有人故意嘲讽我", r"大家都在排斥我", r"被校园欺凌", r"被集体孤立", r"他们故意不带我", r"一直被嘲笑"],
        "response_strategy": "优先肯定用户感受并强调不应独自承受；建议及时保留信息、寻求老师辅导员或学校支持渠道，不鼓励私下激烈对抗。",
    },
    {
        "code": "career_confusion",
        "label": "就业或发展迷茫",
        "level": "medium",
        "patterns": [r"不知道以后干什么", r"对未来很迷茫", r"找不到方向", r"不知道选什么工作", r"感觉前途很迷茫", r"不知道适合什么", r"不知道要不要考研", r"就业压力太大", r"未来一片空白", r"完全不知道下一步", r"越想未来越慌"],
        "response_strategy": "避免直接灌输大道理；帮助用户先缩小选择范围，从兴趣、能力、现实机会三个维度拆解方向判断。",
    },
    {
        "code": "family_pressure",
        "label": "家庭压力明显",
        "level": "medium",
        "patterns": [r"家里给我压力很大", r"父母总是逼我", r"家里总拿我比较", r"父母不理解我", r"家里只看成绩", r"一和家里沟通就很累", r"被家里安排得喘不过气", r"家里一直管着我", r"回家就觉得压抑", r"父母总否定我"],
        "response_strategy": "不要简单要求用户忍耐；帮助用户先理清压力来源，再考虑如何表达真实感受、设置边界或寻找中间支持者沟通。",
    },
    {
        "code": "financial_stress",
        "label": "经济压力明显",
        "level": "medium",
        "patterns": [r"没钱了", r"生活费不够", r"经济压力很大", r"想兼职但撑不住", r"学费压力", r"家里负担不起", r"最近特别缺钱", r"怕没钱吃饭", r"又不敢跟家里开口", r"手头已经撑不住了"],
        "response_strategy": "先承认经济压力的现实性，不做空泛安慰；优先建议盘点紧急需求、校园资助和可行兼职路径，避免高风险借贷。",
    },
    {
        "code": "internet_addiction_risk",
        "label": "网络沉迷倾向",
        "level": "medium",
        "patterns": [r"刷手机停不下来", r"一直玩游戏", r"熬夜打游戏", r"短视频刷太多", r"控制不住玩手机", r"天天打游戏", r"晚上一直刷视频", r"手机一拿起来就停不下", r"每天都在短视频里耗着", r"一玩就停不下来"],
        "response_strategy": "不要简单斥责自制力差；帮助用户识别触发场景，先减少连续沉迷时长，再建立替代行为和作息边界。",
    },
    {
        "code": "emotional_relationship_distress",
        "label": "情感关系受挫",
        "level": "medium",
        "patterns": [r"失恋", r"分手了", r"感情上很难受", r"被喜欢的人拒绝", r"谈恋爱影响状态", r"感情让我很痛苦", r"因为感情什么都做不下去", r"被冷暴力", r"对方不理我我就崩", r"谈个恋爱把自己搞垮了"],
        "response_strategy": "先尊重情感受挫带来的失落，不贬低或简单说“想开点”；帮助用户稳定日常节律，避免把全部自我价值绑在关系结果上。",
    },
    {
        "code": "value_confusion",
        "label": "价值迷茫或意义感不足",
        "level": "medium",
        "patterns": [r"不知道努力有什么意义", r"感觉一切都没意义", r"不知道坚持为了什么", r"觉得做什么都空", r"找不到意义", r"感觉生活没有目标", r"不知道自己为什么要这么累", r"觉得每天都白过", r"活得很空", r"整天像在硬撑"],
        "response_strategy": "不要直接灌输抽象口号；帮助用户把意义感问题落回当下生活、关系和可实现的小目标上，逐步重建方向感。",
    },
    {
        "code": "academic_integrity_risk",
        "label": "学业诚信风险",
        "level": "high",
        "patterns": [r"怎么作弊", r"帮我作弊", r"代写", r"抄作业", r"论文造假", r"怎么蒙混过关", r"怎么逃课不被发现"],
        "response_strategy": "明确拒绝不诚信路径，强调学业诚信和后果；把对话引导回补救、复习、沟通和正当解决办法。",
    },
    {
        "code": "self_harm_risk",
        "label": "疑似自伤或极端表达风险",
        "level": "high",
        "patterns": [r"不想活了", r"活着没意思", r"想结束自己", r"想自杀", r"不如死了", r"想消失", r"不想再撑了", r"我死了算了", r"没有必要活着"],
        "response_strategy": "立即采用安全优先的回应方式，明确表达关心，鼓励马上联系身边可信任的人、老师或专业心理援助；不要进行说教或冷处理。",
    },
    {
        "code": "illegal_or_harmful_intent",
        "label": "疑似违规或有害倾向",
        "level": "high",
        "patterns": [r"报复", r"打人", r"骗", r"作弊", r"攻击", r"搞破坏", r"威胁别人", r"整他", r"报复同学", r"泄露隐私"],
        "response_strategy": "明确劝阻风险行为，强调后果和边界，并引导回到合法、理性、可求助的解决路径。",
    },
]

# ======================== 辅助函数 ========================
def sanitize_ai_text(text: str) -> str:
    if not text:
        return ""
    cleaned = text.replace("\r\n", "\n")
    cleaned = re.sub(r"\n{4,}", "\n\n\n", cleaned)
    return cleaned.strip()

def assess_question_risk(user_text: str, explicit_data: Optional[Dict[str, List[str]]] = None) -> Dict[str, Any]:
    matched_items: List[Dict[str, str]] = []
    normalized_text = re.sub(r"\s+", "", user_text or "")
    for rule in QUESTION_RISK_RULES:
        for pattern in rule["patterns"]:
            if re.search(pattern, normalized_text, re.IGNORECASE):
                matched_items.append({
                    "code": rule["code"], "label": rule["label"], "level": rule["level"],
                    "matched_pattern": pattern, "response_strategy": rule["response_strategy"],
                })
                break
    if explicit_data and explicit_data.get("explicit_topics"):
        topics = explicit_data.get("explicit_topics", [])
        if any(topic in {"学习", "作业", "考试", "课程", "成绩"} for topic in topics) and re.search(r"不想|学不下去|厌学|摆烂", normalized_text):
            if not any(item["code"] == "learning_attitude_negative" for item in matched_items):
                matched_items.append({"code": "learning_attitude_negative", "label": "学习态度消极", "level": "medium", "matched_pattern": "topic+negative_intent", "response_strategy": QUESTION_RISK_RULES[0]["response_strategy"]})
        if any(topic in {"考试", "复习", "成绩", "挂科"} for topic in topics) and re.search(r"慌|紧张|怕|焦虑|考砸|失眠", normalized_text):
            if not any(item["code"] == "exam_anxiety" for item in matched_items):
                matched_items.append({"code": "exam_anxiety", "label": "考试焦虑明显", "level": "medium", "matched_pattern": "topic+exam_anxiety", "response_strategy": QUESTION_RISK_RULES[1]["response_strategy"]})
        if any(topic in {"就业", "考研", "未来", "方向", "工作"} for topic in topics) and re.search(r"迷茫|不知道|没方向|焦虑", normalized_text):
            if not any(item["code"] == "career_confusion" for item in matched_items):
                matched_items.append({"code": "career_confusion", "label": "就业或发展迷茫", "level": "medium", "matched_pattern": "topic+career_confusion", "response_strategy": QUESTION_RISK_RULES[11]["response_strategy"]})
    level_priority = {"low": 0, "medium": 1, "high": 2}
    highest_item = None
    for item in matched_items:
        if highest_item is None or level_priority[item["level"]] > level_priority[highest_item["level"]]:
            highest_item = item
    if highest_item is None:
        return {"detected": False, "risk_level": "low", "primary_label": "未识别到明显风险信号", "matched_items": [], "response_strategy": "正常进行个性化分析和建议，保持具体、自然、有支持感。"}
    return {"detected": True, "risk_level": highest_item["level"], "primary_label": highest_item["label"], "matched_items": matched_items, "response_strategy": highest_item["response_strategy"]}

def build_risk_prompt_block(risk_assessment: Optional[Dict[str, Any]]) -> str:
    if not risk_assessment:
        return ""
    matched_items = cast(List[Dict[str, str]], risk_assessment.get("matched_items") or [])
    matched_labels = [item.get("label", "") for item in matched_items if item.get("label")]
    matched_labels_json = json.dumps(matched_labels, ensure_ascii=False)
    return f"\n    【当前提问风险判定】\n    - 是否检测到风险信号：{'是' if risk_assessment.get('detected') else '否'}\n    - 风险等级：{risk_assessment.get('risk_level', 'low')}\n    - 主要判定：{risk_assessment.get('primary_label', '未识别到明显风险信号')}\n    - 命中的风险类别：{matched_labels_json}\n    - 回应策略：{risk_assessment.get('response_strategy', '')}\n    "

# ======================== 数据库工具函数 ========================
def get_db_connection():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        logger.info("SQLite 数据库连接成功")
        return conn
    except sqlite3.Error as e:
        logger.error(f"数据库连接失败: {str(e)}")
        raise HTTPException(status_code=500, detail="数据库连接异常")

def generate_conversation_title(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if not cleaned:
        return "新对话"
    return f"{cleaned[:18]}..." if len(cleaned) > 18 else cleaned

def serialize_conversation(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": record.get("id"), "user_id": record.get("user_id"), "title": record.get("title") or "新对话",
        "created_at": str(record.get("created_at") or ""), "updated_at": str(record.get("updated_at") or ""),
        "message_count": int(record.get("message_count") or 0), "last_message": record.get("last_message") or ""
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
        "id": record.get("id"), "topic": topic, "category": DISCUSSION_TOPIC_TO_CATEGORY.get(topic, "未分类"),
        "title": record.get("title") or topic, "content": record.get("content") or "",
        "author": record.get("author") or "匿名用户", "created_at": str(record.get("created_at") or ""),
        "like_count": int(record.get("like_count") or 0), "report_count": int(record.get("report_count") or 0),
        "user_liked": bool(record.get("user_liked") or False), "user_reported": bool(record.get("user_reported") or False),
    }

def get_user_id_by_username(conn, username: str) -> int:
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    cursor.close()
    if not row:
        raise HTTPException(status_code=404, detail="用户不存在")
    return row[0]

def get_discussion_post_by_id(conn, post_id: int) -> Dict[str, Any]:
    cursor = conn.cursor()
    cursor.execute("SELECT id, user_id, topic, title, content, created_at, like_count, report_count FROM discussion_posts WHERE id = ?", (post_id,))
    row = cursor.fetchone()
    cursor.close()
    if not row:
        raise HTTPException(status_code=404, detail="帖子不存在")
    return dict(row)

def fetch_discussion_post_detail(conn, post_id: int, viewer_user_id: Optional[int] = None) -> Dict[str, Any]:
    cursor = conn.cursor()
    if viewer_user_id is None:
        cursor.execute("""
            SELECT p.id, p.topic, p.title, p.content, p.created_at, p.like_count, p.report_count, u.username AS author,
                   0 AS user_liked, 0 AS user_reported
            FROM discussion_posts p INNER JOIN users u ON u.id = p.user_id WHERE p.id = ?
        """, (post_id,))
    else:
        cursor.execute("""
            SELECT p.id, p.topic, p.title, p.content, p.created_at, p.like_count, p.report_count, u.username AS author,
                   CASE WHEN l.id IS NULL THEN 0 ELSE 1 END AS user_liked,
                   CASE WHEN r.id IS NULL THEN 0 ELSE 1 END AS user_reported
            FROM discussion_posts p
            INNER JOIN users u ON u.id = p.user_id
            LEFT JOIN discussion_post_likes l ON l.post_id = p.id AND l.user_id = ?
            LEFT JOIN discussion_post_reports r ON r.post_id = p.id AND r.user_id = ?
            WHERE p.id = ?
        """, (viewer_user_id, viewer_user_id, post_id))
    row = cursor.fetchone()
    cursor.close()
    if not row:
        raise HTTPException(status_code=404, detail="帖子不存在")
    return dict(row)

def ensure_users_role_schema():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 创建 users 表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                identity TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                age_group TEXT NOT NULL,
                current_major TEXT NOT NULL
             );
        """)
        # 创建 user_portraits 表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_portraits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                ideal_belief INTEGER,
                logic_thinking INTEGER,
                practice_ability INTEGER,
                psychological_quality INTEGER,
                emotional_state INTEGER,
                hidden_need TEXT,
                tags TEXT,
                chat_content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                current_major TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        conn.commit()
    except Exception as e:
        logger.error(f"建表失败: {e}")
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

def ensure_chat_conversation_schema() -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("CREATE TABLE IF NOT EXISTS chat_conversations (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, title VARCHAR(255) NOT NULL DEFAULT '新对话', created_at DATETIME DEFAULT CURRENT_TIMESTAMP, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_conversations_user_id ON chat_conversations (user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_conversations_updated_at ON chat_conversations (updated_at)")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, conversation_id INTEGER DEFAULT NULL,
                user_message TEXT NOT NULL, user_emotion_score DECIMAL(5,2) DEFAULT NULL, user_ideal_belief DECIMAL(5,2) DEFAULT NULL,
                user_logic_thinking DECIMAL(5,2) DEFAULT NULL, user_practice_ability DECIMAL(5,2) DEFAULT NULL,
                user_psychological_quality DECIMAL(5,2) DEFAULT NULL, user_hidden_needs TEXT DEFAULT NULL,
                user_interest_themes TEXT DEFAULT NULL, ai_reply TEXT NOT NULL, ai_reply_score INT DEFAULT NULL,
                ai_reply_feedback TEXT DEFAULT NULL, selected_model VARCHAR(50) DEFAULT NULL, qwen_score INT DEFAULT NULL,
                deepseek_score INT DEFAULT NULL, kimi_score INT DEFAULT NULL, created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_history_user_id ON chat_history (user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_history_conversation_id ON chat_history (conversation_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_history_created_at ON chat_history (created_at)")
        cursor.execute("PRAGMA table_info(chat_history)")
        if 'conversation_id' not in [col[1] for col in cursor.fetchall()]:
            cursor.execute("ALTER TABLE chat_history ADD COLUMN conversation_id INTEGER DEFAULT NULL")
            cursor.execute("CREATE INDEX idx_chat_history_conversation_id ON chat_history (conversation_id)")
        cursor.execute("SELECT DISTINCT user_id FROM chat_history WHERE conversation_id IS NULL")
        for row in cursor.fetchall():
            user_id = row[0]
            cursor.execute("SELECT id FROM chat_conversations WHERE user_id = ? AND title = '历史对话' ORDER BY id ASC LIMIT 1", (user_id,))
            leg = cursor.fetchone()
            if leg:
                conv_id = leg[0]
            else:
                cursor.execute("INSERT INTO chat_conversations (user_id, title) VALUES (?, '历史对话')", (user_id,))
                conv_id = cursor.lastrowid
            cursor.execute("UPDATE chat_history SET conversation_id = ? WHERE user_id = ? AND conversation_id IS NULL", (conv_id, user_id))
        conn.commit()
    except Exception as e:
        logger.error(f"初始化聊天会话结构失败: {str(e)}")
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

def ensure_discussion_schema() -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS discussion_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, topic VARCHAR(120) NOT NULL,
                title VARCHAR(255) NOT NULL, content TEXT NOT NULL, like_count INTEGER NOT NULL DEFAULT 0,
                report_count INTEGER NOT NULL DEFAULT 0, created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_discussion_posts_topic_created_at ON discussion_posts (topic, created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_discussion_posts_user_id ON discussion_posts (user_id)")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS discussion_post_likes (
                id INTEGER PRIMARY KEY AUTOINCREMENT, post_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP, UNIQUE(post_id, user_id)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_discussion_post_likes_user_id ON discussion_post_likes (user_id)")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS discussion_post_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT, post_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP, UNIQUE(post_id, user_id)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_discussion_post_reports_user_id ON discussion_post_reports (user_id)")
        conn.commit()
    except Exception as e:
        logger.error(f"初始化讨论区结构失败: {str(e)}")
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

def create_conversation_for_user(conn, user_id: int, title: Optional[str] = None) -> Dict[str, Any]:
    cursor = conn.cursor()
    cursor.execute("INSERT INTO chat_conversations (user_id, title) VALUES (?, ?)", (user_id, title or "新对话"))
    conv_id = cursor.lastrowid
    conn.commit()
    cursor.execute("SELECT id, user_id, title, created_at, updated_at FROM chat_conversations WHERE id = ?", (conv_id,))
    row = cursor.fetchone()
    cursor.close()
    return dict(row)

def get_conversation_for_user(conn, user_id: int, conversation_id: int) -> Dict[str, Any]:
    cursor = conn.cursor()
    cursor.execute("SELECT id, user_id, title, created_at, updated_at FROM chat_conversations WHERE id = ? AND user_id = ?", (conversation_id, user_id))
    row = cursor.fetchone()
    cursor.close()
    if not row:
        raise HTTPException(status_code=404, detail="会话不存在")
    return dict(row)

def get_user_portrait(user_id: int) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT ideal_belief, logic_thinking, practice_ability, psychological_quality, emotional_state, hidden_need, tags, current_major FROM user_portraits WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id,))
        row = cursor.fetchone()
        if row:
            tags = row[6].split(",") if row[6] else []
            hidden = row[5].split(",") if row[5] else []
            return {"ideal": row[0] or 80, "logic": row[1] or 80, "practice": row[2] or 70, "psychological": row[3] or 75, "emotion": row[4] or 70, "learning_preference": [t.strip() for t in tags if t.strip()][:6], "hidden_needs": [h.strip() for h in hidden if h.strip()][:6], "current_major": row[7] or "未设置"}
        else:
            return {"ideal": 80, "logic": 80, "practice": 70, "psychological": 75, "emotion": 70, "learning_preference": [], "hidden_needs": [], "current_major": "未设置"}
    finally:
        cursor.close()
        conn.close()

# ======================== 新闻抓取函数（原样保留） ========================
def strip_html_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", "", unescape(text or ""))

def should_include_news_item(title: str, article_url: str, source: Dict[str, Any]) -> bool:
    normalized_title = re.sub(r"\s+", " ", title).strip()
    if len(normalized_title) < 8: return False
    if any(excluded in normalized_title for excluded in NEWS_EXCLUDED_TITLES): return False
    parsed_url = urlparse(article_url)
    if parsed_url.scheme not in {"http", "https"}: return False
    if parsed_url.netloc not in source["allowed_domains"]: return False
    return any(keyword in normalized_title for keyword in NEWS_TITLE_KEYWORDS) or any(keyword in parsed_url.path for keyword in source["path_keywords"])

def extract_news_items_from_html(page_html: str, source: Dict[str, Any], limit: int = 6) -> List[Dict[str, str]]:
    seen_pairs = set()
    items = []
    for href, inner_html in re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', page_html, flags=re.IGNORECASE | re.DOTALL):
        article_url = urljoin(source["url"], href)
        title = strip_html_tags(inner_html)
        title = re.sub(r"\s+", " ", title).strip()
        if not should_include_news_item(title, article_url, source): continue
        key = (title, article_url)
        if key in seen_pairs: continue
        seen_pairs.add(key)
        items.append({"title": title, "url": article_url, "source": source["name"]})
        if len(items) >= limit: break
    return items

def fetch_daily_news(limit: int = 6) -> List[Dict[str, str]]:
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0 Safari/537.36"})
    collected = []
    seen_urls = set()
    for source in NEWS_SOURCES:
        try:
            response = session.get(source["url"], timeout=10)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding
            items = extract_news_items_from_html(response.text, source, limit=limit)
            for it in items:
                if it["url"] not in seen_urls:
                    seen_urls.add(it["url"])
                    collected.append(it)
                    if len(collected) >= limit: return collected
        except Exception as e:
            logger.warning(f"抓取 {source['name']} 新闻失败: {str(e)}")
    return collected

def extract_recommendation_keywords(portrait: Dict[str, Any]) -> List[str]:
    raw = []
    raw.extend(portrait.get("learning_preference", []))
    raw.extend(portrait.get("hidden_needs", []))
    if portrait.get("current_major") and portrait["current_major"] != "未设置":
        raw.append(portrait["current_major"])
    expanded = []
    for kw in raw:
        kw = re.sub(r"\s+", "", str(kw))
        if not kw: continue
        expanded.append(kw)
        for trigger, mapped in INTEREST_KEYWORD_MAP.items():
            if trigger in kw:
                expanded.extend(mapped)
    seen = set()
    ordered = []
    for kw in expanded:
        if kw not in seen:
            seen.add(kw)
            ordered.append(kw)
    return ordered[:18]

def score_news_for_keywords(item: Dict[str, str], keywords: List[str]) -> Dict[str, Any]:
    title = item.get("title", "")
    source = item.get("source", "")
    article_text = f"{title} {source}"
    matched = [kw for kw in keywords if kw and kw in article_text]
    score = sum((3 if kw in title else 1) for kw in matched)
    if any(token in title for token in ["青年", "思政", "教育", "国家安全", "理论", "文化"]):
        score += 2
    return {**item, "score": score, "matched_keywords": matched[:4]}

def fetch_recommended_news_for_user(username: str, limit: int = 6) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="用户不存在")
        user_id = row[0]
        portrait = get_user_portrait(user_id)
        keywords = extract_recommendation_keywords(portrait)
        candidate_news = fetch_daily_news(limit=max(limit * 3, 12))
        scored = [score_news_for_keywords(it, keywords) for it in candidate_news]
        scored.sort(key=lambda x: (x.get("score", 0), len(x.get("matched_keywords", []))), reverse=True)
        rec = [it for it in scored if it.get("score", 0) > 0][:limit]
        if len(rec) < limit:
            used = {it["url"] for it in rec}
            fallback = [it for it in scored if it["url"] not in used][:limit - len(rec)]
            rec.extend(fallback)
        return {"portrait_keywords": keywords[:8], "news": rec[:limit]}
    finally:
        cursor.close()
        conn.close()

# ======================== NLP 相关函数 ========================
def nlp_pre_processing(text: str) -> Dict[str, List[str]]:
    STOPWORDS = set(["的", "了", "是", "我", "你", "他", "她", "它", "们", "在", "有", "就", "不", "也", "还", "这", "那", "个", "种", "类", "都", "而", "及", "与", "等", "和", "对", "对于", "关于"])
    SYNONYM_DICT = {"二十大": ["党的二十大", "二十大报告"], "乡村振兴": ["乡村建设", "乡村发展", "三农"], "社会主义核心价值观": ["核心价值观", "价值观"], "党史学习": ["学党史", "党史教育", "党史"], "内卷": ["内耗", "过度竞争"], "焦虑": ["压力大", "迷茫", "困惑"], "自立自强": ["自主创新", "科技自立", "核心技术"]}
    words = pseg.cut(text)
    identities = []
    topics = []
    identity_keywords = {'学生', '党员', '积极分子', '预备党员','团员', '青年','思政课代表','思政老师', '教师', '辅导员', '志愿者'}
    politics_topics = []
    for word, flag in words:
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
    return {"identities": list(set(identities)), "politics_topics": list(set(politics_topics)), "explicit_topics": list(set(topics))}

def dynamic_semantic_completion(text: str) -> List[str]:
    rules = {
        r"资源.*(零散|乱|杂|找不到)": "对结构化知识体系的需求",
        r"(迷茫|不知道|困惑|无方向)": "对个性化生涯规划引导的需求",
        r"(内卷|压力|焦虑|疲惫)": "对心理疏导与价值观重塑的需求",
        r"(自立自强|核心技术|科技)": "对科技报国志向的强化需求",
        r"(党史|学习|了解)": "对系统化理论学习的需求",
        r"(乡村|农村|农民)": "对乡村振兴政策理解的需求"
    }
    needs = []
    for pat, need in rules.items():
        if re.search(pat, text):
            needs.append(need)
    return needs

def analyze_sentiment_with_bert(text: str) -> Dict[str, Any]:
    if bert_tokenizer is None or bert_model is None:
        return {"sentiment_score": None, "confidence": 0.0, "label": "未知"}
    try:
        inputs = bert_tokenizer(text, return_tensors="pt", truncation=True, max_length=512, padding=True)
        with torch.no_grad():
            outputs = bert_model(**inputs)
            logits = outputs.logits
            probs = torch.softmax(logits, dim=-1)
        pred_class = torch.argmax(probs, dim=-1).item()
        conf = probs[0][pred_class].item()
        if pred_class == 1:
            score = 50 + int(conf * 50)
            label = "积极"
        else:
            score = 50 - int(conf * 50)
            label = "消极"
        return {"sentiment_score": score, "confidence": round(conf, 3), "label": label}
    except Exception as e:
        logger.error(f"BERT情感分析失败: {str(e)}")
        return {"sentiment_score": None, "confidence": 0.0, "label": "分析失败"}

def enhance_user_portrait(user_text: str, user_identity: str, user_age_group: str, historical_context: Dict[str, Any], explicit_data: Dict[str, List[str]]) -> Dict[str, Any]:
    bert_sentiment = analyze_sentiment_with_bert(user_text)
    rule_needs = historical_context.get("rule_based_needs", [])
    rule_needs_str = "、".join(rule_needs) if rule_needs else "未检测到特定触发词"
    bert_info = ""
    if bert_sentiment["sentiment_score"] is not None:
        bert_info = f"\n    【BERT情感分析结果】\n    - 情感倾向：{bert_sentiment['label']}\n    - 情感得分：{bert_sentiment['sentiment_score']}/100\n    - 置信度：{bert_sentiment['confidence']*100:.1f}%\n    "
    system_prompt = f"""
    你现在是思政教育系统的用户画像分析专家。
    【用户基本信息】身份：{user_identity}，年龄段：{user_age_group}{bert_info}
    【NLP提取的显性特征】身份关键词：{json.dumps(explicit_data.get('identities', []))}，政治话题：{json.dumps(explicit_data.get('politics_topics', []))}，话题：{json.dumps(explicit_data.get('explicit_topics', []))}
    【本地规则识别到的潜在需求】预警信号：{rule_needs_str}
    【历史画像参考】历史标签：{json.dumps(historical_context.get('historical_tags', []))}，历史隐性需求：{json.dumps(historical_context.get('historical_hidden_needs', []))}
    必须严格返回 JSON 格式：{{"sentiment_score": 50-100, "logic_score": 50-100, "practice_ability": 50-100, "psychological_quality": 50-100, "emotional_state": 50-100, "interest_themes": ["主题1","主题2","主题3"], "hidden_needs": ["需求1","需求2"], "user_tags": ["标签1","标签2","标签3"], "analysis_summary": "用户画像分析总结"}}
    """
    response = dashscope.Generation.call(model=dashscope.Generation.Models.qwen_turbo, messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_text}], result_format="message")
    if response.status_code != HTTPStatus.OK:
        raise Exception("第一阶段大模型API调用失败")
    portrait = json.loads(response.output.choices[0]["message"]["content"])
    portrait.setdefault("practice_ability", portrait.get("logic_score", 70))
    portrait.setdefault("psychological_quality", portrait.get("sentiment_score", 70))
    portrait.setdefault("emotional_state", portrait.get("sentiment_score", 70))
    return portrait

def build_personalized_system_prompt(portrait_data: Dict[str, Any], user_identity: str, user_age_group: str, user_major: str, explicit_data: Dict[str, List[str]], risk_assessment: Optional[Dict[str, Any]] = None) -> str:
    risk_block = build_risk_prompt_block(risk_assessment)
    return f"""
    你现在是思政教育系统的资深导师。
    【用户基本信息】身份：{user_identity}，年龄段：{user_age_group}，专业：{user_major}
    【用户显性特征】身份：{json.dumps(explicit_data.get('identities', []))}，关注话题：{json.dumps(explicit_data.get('explicit_topics', []))}，政治话题：{json.dumps(explicit_data.get('politics_topics', []))}
    【用户画像分析结果】理想信念强度：{portrait_data['sentiment_score']}/100，逻辑思维能力：{portrait_data['logic_score']}/100，实践能力：{portrait_data.get('practice_ability', portrait_data['logic_score'])}/100，心理素质：{portrait_data.get('psychological_quality', portrait_data['sentiment_score'])}/100，情感状态：{portrait_data.get('emotional_state', portrait_data['sentiment_score'])}/100，兴趣主题：{json.dumps(portrait_data['interest_themes'])}，隐性需求：{json.dumps(portrait_data['hidden_needs'])}，用户标签：{json.dumps(portrait_data['user_tags'])}，画像分析：{portrait_data['analysis_summary']}{risk_block}
    请提供有温度、有深度的导师回复（不需要JSON，直接返回回复文本）。
    """

def generate_personalized_response(user_text: str, portrait_data: Dict[str, Any], user_identity: str, user_age_group: str, user_major: str = "未设置", explicit_data: Optional[Dict[str, List[str]]] = None, risk_assessment: Optional[Dict[str, Any]] = None) -> str:
    if explicit_data is None:
        explicit_data = {"identities": [], "explicit_topics": [], "politics_topics": []}
    system = build_personalized_system_prompt(portrait_data, user_identity, user_age_group, user_major, explicit_data, risk_assessment)
    response = dashscope.Generation.call(model=dashscope.Generation.Models.qwen_turbo, messages=[{"role": "system", "content": system}, {"role": "user", "content": user_text}], result_format="message")
    if response.status_code != HTTPStatus.OK:
        raise Exception("第二阶段大模型API调用失败")
    reply = sanitize_ai_text(response.output.choices[0]["message"]["content"])
    return reply

def generate_response_with_deepseek(user_text: str, portrait_data: Dict[str, Any], user_identity: str, user_age_group: str, user_major: str = "未设置", explicit_data: Optional[Dict[str, List[str]]] = None, risk_assessment: Optional[Dict[str, Any]] = None) -> str:
    if explicit_data is None:
        explicit_data = {"identities": [], "explicit_topics": [], "politics_topics": []}
    system = build_personalized_system_prompt(portrait_data, user_identity, user_age_group, user_major, explicit_data, risk_assessment)
    try:
        response = deepseek_client.chat.completions.create(model=DEEPSEEK_MODEL_ID, messages=[{"role": "system", "content": system}, {"role": "user", "content": user_text}], temperature=0.7, max_tokens=2048)
        return sanitize_ai_text(response.choices[0].message.content or "")
    except Exception as e:
        raise Exception(f"DeepSeek 调用失败: {str(e)}")

def generate_response_with_kimi(user_text: str, portrait_data: Dict[str, Any], user_identity: str, user_age_group: str, user_major: str = "未设置", explicit_data: Optional[Dict[str, List[str]]] = None, risk_assessment: Optional[Dict[str, Any]] = None) -> str:
    if explicit_data is None:
        explicit_data = {"identities": [], "explicit_topics": [], "politics_topics": []}
    system = build_personalized_system_prompt(portrait_data, user_identity, user_age_group, user_major, explicit_data, risk_assessment)
    try:
        response = kimi_client.chat.completions.create(model=KIMI_MODEL_ID, messages=[{"role": "system", "content": system}, {"role": "user", "content": user_text}], temperature=0.7, max_tokens=2048)
        return sanitize_ai_text(response.choices[0].message.content or "")
    except Exception as e:
        raise Exception(f"Kimi 调用失败: {str(e)}")

def generate_responses_dual_models(user_text: str, portrait_data: Dict[str, Any], user_identity: str, user_age_group: str, user_major: str = "未设置", explicit_data: Optional[Dict[str, List[str]]] = None, risk_assessment: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    if explicit_data is None:
        explicit_data = {"identities": [], "explicit_topics": [], "politics_topics": []}
    replies = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        f1 = executor.submit(generate_personalized_response, user_text, portrait_data, user_identity, user_age_group, user_major, explicit_data, risk_assessment)
        f2 = executor.submit(generate_response_with_deepseek, user_text, portrait_data, user_identity, user_age_group, user_major, explicit_data, risk_assessment)
        f3 = executor.submit(generate_response_with_kimi, user_text, portrait_data, user_identity, user_age_group, user_major, explicit_data, risk_assessment)
        try: replies["qwen"] = f1.result(timeout=60)
        except Exception as e: replies["qwen"] = ""
        try: replies["deepseek"] = f2.result(timeout=60)
        except Exception as e: replies["deepseek"] = ""
        try: replies["kimi"] = f3.result(timeout=60)
        except Exception as e: replies["kimi"] = ""
    return replies

# ======================== 评分与 RAG 相关 ========================
SCORE_DIMENSIONS = ["理论贯彻度", "主流意识形态弘扬", "政治立场引导", "社会主义核心价值观传播", "品德与人格塑造", "理想信念培育", "社会发展适配", "热点融入度", "学生需求契合", "个性与专业适配", "成长增量体现"]

def _extract_json(text: str) -> Dict[str, Any]:
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise ValueError("未找到JSON内容")
    return json.loads(match.group(0))

def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return default

def score_ai_response(user_text: str, reply_text: str, portrait_data: Dict[str, Any], rag_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    portrait_json = json.dumps(portrait_data, ensure_ascii=False)
    rag_summary = ""
    if rag_info:
        try:
            if rag_info.get("available"):
                diff = rag_info.get("difference_flag", False)
                max_dist = rag_info.get("max_distance")
                rag_summary = f"RAG审查可用: True\n差异显著: {diff}\n最大距离: {max_dist}\n"
            else:
                rag_summary = f"RAG不可用: {rag_info.get('reason', '')}\n"
        except:
            rag_summary = ""
    system_prompt = f"""
    你是一个严格的回复质量评估器。用户画像：{portrait_json} {rag_summary}
    评分范围 0-100。若分数低于80，请给出可执行的改进意见；若>=80，可给出简短肯定。
    必须严格返回 JSON：{{"score": 0-100, "feedback": "...", "dimension_scores": {{"理论贯彻度":0-10,"主流意识形态弘扬":0-10,"政治立场引导":0-10,"社会主义核心价值观传播":0-10,"品德与人格塑造":0-10,"理想信念培育":0-10,"社会发展适配":0-10,"热点融入度":0-10,"学生需求契合":0-10,"个性与专业适配":0-10,"成长增量体现":0-10}}}}
    """
    response = dashscope.Generation.call(model=dashscope.Generation.Models.qwen_max, messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": f"用户问题：{user_text}\n\nAI回复：{reply_text}"}], result_format="message")
    if response.status_code != HTTPStatus.OK:
        raise Exception("回复评分大模型API调用失败")
    raw = response.output.choices[0]["message"]["content"]
    try:
        data = json.loads(raw)
    except:
        data = _extract_json(raw)
    total = max(0, min(100, _safe_int(data.get("score", 0))))
    feedback = str(data.get("feedback", "")).strip()
    dims = {dim: max(0, min(10, _safe_int(data.get("dimension_scores", {}).get(dim, 0)))) for dim in SCORE_DIMENSIONS}
    return {"score": total, "feedback": feedback, "dimension_scores": dims}

_CHROMADB_CLIENT = None
_CHROMADB_COLLECTION = None

def _get_chromadb_collection():
    global _CHROMADB_CLIENT, _CHROMADB_COLLECTION
    if _CHROMADB_COLLECTION is not None:
        return _CHROMADB_COLLECTION
    try:
        import chromadb
        if _CHROMADB_CLIENT is None:
            try:
                _CHROMADB_CLIENT = chromadb.PersistentClient(path="./my_sizheng_db")
            except:
                _CHROMADB_CLIENT = chromadb.Client()
        if hasattr(_CHROMADB_CLIENT, 'get_or_create_collection'):
            _CHROMADB_COLLECTION = _CHROMADB_CLIENT.get_or_create_collection(name='political_education_v1')
        elif hasattr(_CHROMADB_CLIENT, 'get_collection'):
            try:
                _CHROMADB_COLLECTION = _CHROMADB_CLIENT.get_collection(name='political_education_v1')
            except:
                pass
        return _CHROMADB_COLLECTION
    except Exception as e:
        logger.warning(f"获取ChromaDB collection失败: {e}")
        return None

def rag_review_reply(reply_text: str, user_text: str, k: int = 3) -> Dict[str, Any]:
    try:
        import numpy as _np
    except:
        return {"available": False, "reason": "numpy缺失"}
    if EMBEDDING_MODEL is None:
        return {"available": False, "reason": "Embedding模型未加载"}
    try:
        coll = _get_chromadb_collection()
        if coll is None:
            return {"available": False, "reason": "向量库未找到"}
        q_emb = EMBEDDING_MODEL.encode(reply_text, convert_to_numpy=True)
        try:
            res = coll.query(query_embeddings=[q_emb.tolist()], n_results=k, include=['documents'])
            docs = []
            if isinstance(res, dict) and 'documents' in res and res['documents']:
                for dl in res['documents']:
                    if isinstance(dl, list):
                        docs.extend(dl)
        except:
            docs = []
        if not docs:
            return {"available": True, "distances": [], "max_distance": None, "difference_flag": False, "evidence": []}
        doc_embs = EMBEDDING_MODEL.encode(docs, convert_to_numpy=True)
        if doc_embs.ndim == 1:
            doc_embs = doc_embs.reshape(1, -1)
        sims = _np.dot(doc_embs, q_emb) / (_np.linalg.norm(doc_embs, axis=1) * _np.linalg.norm(q_emb) + 1e-12)
        distances = (1.0 - sims).tolist()
        maxd = max(distances)
        diff = any(d > 0.8 for d in distances)
        return {"available": True, "distances": distances, "max_distance": float(maxd), "difference_flag": diff, "evidence": docs}
    except Exception as e:
        logger.exception("RAG 审查内部错误")
        return {"available": False, "reason": str(e)}

def regenerate_response_with_feedback(user_text: str, reply_text: str, feedback: str, portrait_data: Dict[str, Any], user_identity: str, user_age_group: str, user_major: str, explicit_data: Dict[str, List[str]]) -> str:
    sys_prompt = build_personalized_system_prompt(portrait_data, user_identity, user_age_group, user_major, explicit_data, None)
    user_prompt = f"请根据以下改进意见重写回复。\n原回复：{reply_text}\n改进意见：{feedback}\n直接输出重写后的回复。"
    response = dashscope.Generation.call(model=dashscope.Generation.Models.qwen_max, messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": user_text}, {"role": "user", "content": user_prompt}], result_format="message")
    if response.status_code != HTTPStatus.OK:
        raise Exception("重写回复失败")
    return sanitize_ai_text(response.output.choices[0]["message"]["content"])

def consolidate_user_tags(all_tags: List[str], all_hidden_needs: List[str]) -> Dict[str, List[str]]:
    system_prompt = f"""
    整合优化用户标签和隐性需求。当前标签：{json.dumps(all_tags)}，当前隐性需求：{json.dumps(all_hidden_needs)}
    去除重复、合并相似、保留核心（标签不超过15，需求不超过5）。返回JSON：{{"consolidated_tags": ["标签1",...], "consolidated_needs": ["需求1",...]}}
    """
    response = dashscope.Generation.call(model=dashscope.Generation.Models.qwen_turbo, messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": "请整合我的标签和需求"}], result_format="message")
    if response.status_code != HTTPStatus.OK:
        raise Exception("第三阶段大模型调用失败")
    data = json.loads(response.output.choices[0]["message"]["content"])
    return {"tags": data.get("consolidated_tags", []), "hidden_needs": data.get("consolidated_needs", [])}

# ======================== 启动事件 ========================
@app.on_event("startup")
async def startup_event():
    ensure_users_role_schema()
    ensure_chat_conversation_schema()
    ensure_discussion_schema()

# ======================== API 路由 ========================
@app.post("/register")
async def register(data: AuthRequest):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT id FROM users WHERE username = ?", (data.username,))
        if c.fetchone():
            return {"status": "fail", "message": "用户名已存在"}
        role = resolve_user_role(data.identity)
        if role == "admin":
            return {"status": "fail", "message": "管理员账号不支持自助注册"}
        identity_val = data.identity.strip() if data.identity else "普通学生"
        c.execute("INSERT INTO users (username, password, identity, role, age_group) VALUES (?, ?, ?, ?, ?)",
                  (data.username, data.password, identity_val, role, data.age_group))
        uid = c.lastrowid
        c.execute("INSERT INTO user_portraits (user_id, ideal_belief, logic_thinking, practice_ability, psychological_quality, emotional_state, hidden_need, tags, current_major, chat_content) VALUES (?, 80, 80, 70, 75, 70, '等待分析...', '', ?, '用户注册')",
                  (uid, data.current_major))
        conn.commit()
        return {"status": "success", "message": "注册成功"}
    except Exception as e:
        conn.rollback()
        logger.error(f"注册失败: {str(e)}")
        return {"status": "error", "message": "注册失败"}
    finally:
        c.close()
        conn.close()

@app.post("/login")
async def login(data: AuthRequest):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT id, username, password, identity, role FROM users WHERE username = ?", (data.username,))
        user = c.fetchone()
        if not user:
            return {"status": "fail", "message": "用户不存在"}
        if data.password != user[2]:
            return {"status": "fail", "message": "密码错误"}
        stored_identity = user[3] or "普通学生"
        stored_role = normalize_db_role(user[4], stored_identity)
        req_role = resolve_user_role(data.identity)
        if req_role != stored_role:
            exp = "管理员" if stored_role == "admin" else "普通用户"
            return {"status": "fail", "message": f"账号类型不匹配，请使用{exp}身份登录"}
        portrait = get_user_portrait(user[0])
        return {"status": "success", "message": "登录成功", "data": {"user_id": user[0], "username": user[1], "identity": stored_identity, "role": stored_role, "portrait": portrait}}
    except Exception as e:
        logger.error(f"登录失败: {str(e)}")
        return {"status": "error", "message": "登录失败"}
    finally:
        c.close()
        conn.close()

@app.get("/chat/history")
async def get_chat_history(username: str, limit: int = 50, offset: int = 0):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT id FROM users WHERE username = ?", (username,))
        row = c.fetchone()
        if not row:
            raise HTTPException(404, "用户不存在")
        uid = row[0]
        c.execute("SELECT id, user_message, ai_reply, user_emotion_score, user_hidden_needs, ai_reply_score, ai_reply_feedback, selected_model, qwen_score, deepseek_score, kimi_score, created_at FROM chat_history WHERE user_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?", (uid, limit, offset))
        records = [dict(r) for r in c.fetchall()]
        for rec in records:
            if rec.get("ai_reply"):
                rec["ai_reply"] = sanitize_ai_text(rec["ai_reply"])
        c.execute("SELECT COUNT(*) FROM chat_history WHERE user_id = ?", (uid,))
        total = c.fetchone()[0]
        return {"status": "success", "data": {"history": records, "total": total, "limit": limit, "offset": offset}}
    finally:
        c.close()
        conn.close()

@app.get("/conversations")
async def get_conversations(username: str):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT id FROM users WHERE username = ?", (username,))
        row = c.fetchone()
        if not row:
            raise HTTPException(404, "用户不存在")
        uid = row[0]
        c.execute("""
            SELECT c.id, c.user_id, c.title, c.created_at, c.updated_at, COUNT(h.id) AS message_count,
                   (SELECT user_message FROM chat_history WHERE conversation_id = c.id ORDER BY created_at DESC LIMIT 1) AS last_message
            FROM chat_conversations c LEFT JOIN chat_history h ON h.conversation_id = c.id
            WHERE c.user_id = ? GROUP BY c.id ORDER BY c.updated_at DESC, c.id DESC
        """, (uid,))
        convs = [serialize_conversation(dict(r)) for r in c.fetchall()]
        return {"status": "success", "data": {"conversations": convs}}
    finally:
        c.close()
        conn.close()

@app.post("/conversations")
async def create_conversation(data: ConversationCreateRequest):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT id FROM users WHERE username = ?", (data.username,))
        row = c.fetchone()
        if not row:
            raise HTTPException(404, "用户不存在")
        conv = create_conversation_for_user(conn, row[0], data.title)
        return {"status": "success", "data": {"conversation": serialize_conversation(conv)}}
    finally:
        c.close()
        conn.close()

@app.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(conversation_id: int, username: str):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT id FROM users WHERE username = ?", (username,))
        row = c.fetchone()
        if not row:
            raise HTTPException(404, "用户不存在")
        uid = row[0]
        get_conversation_for_user(conn, uid, conversation_id)
        c.execute("SELECT id, conversation_id, user_message, ai_reply, user_emotion_score, user_hidden_needs, ai_reply_score, ai_reply_feedback, selected_model, qwen_score, deepseek_score, kimi_score, created_at FROM chat_history WHERE user_id = ? AND conversation_id = ? ORDER BY created_at ASC", (uid, conversation_id))
        msgs = []
        for r in c.fetchall():
            rec = dict(r)
            if rec.get("ai_reply"):
                rec["ai_reply"] = sanitize_ai_text(rec["ai_reply"])
            msgs.append(rec)
        return {"status": "success", "data": {"conversation_id": conversation_id, "messages": msgs}}
    finally:
        c.close()
        conn.close()

@app.get("/chat/history/{chat_id}")
async def get_chat_detail(chat_id: int):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT id, user_id, user_message, ai_reply, user_emotion_score, user_ideal_belief, user_logic_thinking, user_practice_ability, user_psychological_quality, user_hidden_needs, user_interest_themes, ai_reply_score, ai_reply_feedback, selected_model, qwen_score, deepseek_score, kimi_score, created_at FROM chat_history WHERE id = ?", (chat_id,))
        rec = c.fetchone()
        if not rec:
            raise HTTPException(404, "聊天记录不存在")
        rec = dict(rec)
        if rec.get("ai_reply"):
            rec["ai_reply"] = sanitize_ai_text(rec["ai_reply"])
        return {"status": "success", "data": rec}
    finally:
        c.close()
        conn.close()

@app.get("/discussion/topics")
async def get_discussion_topics():
    return {"status": "success", "data": {"categories": DISCUSSION_TOPIC_CATEGORIES, "flat_topics": list(DISCUSSION_TOPIC_TO_CATEGORY.keys())}}

@app.get("/discussion/posts")
async def get_discussion_posts(topic: str, username: Optional[str] = None, limit: int = 50, offset: int = 0):
    norm_topic = re.sub(r"\s+", " ", topic or "").strip()
    if norm_topic not in DISCUSSION_TOPIC_TO_CATEGORY:
        raise HTTPException(400, "讨论主题不存在")
    conn = get_db_connection()
    c = conn.cursor()
    try:
        viewer_id = None
        if username:
            viewer_id = get_user_id_by_username(conn, username)
        if viewer_id is None:
            c.execute("SELECT p.id, p.topic, p.title, p.content, p.created_at, p.like_count, p.report_count, u.username AS author, 0 AS user_liked, 0 AS user_reported FROM discussion_posts p JOIN users u ON u.id = p.user_id WHERE p.topic = ? ORDER BY p.created_at DESC LIMIT ? OFFSET ?", (norm_topic, limit, offset))
        else:
            c.execute("""
                SELECT p.id, p.topic, p.title, p.content, p.created_at, p.like_count, p.report_count, u.username AS author,
                       CASE WHEN l.id IS NULL THEN 0 ELSE 1 END AS user_liked,
                       CASE WHEN r.id IS NULL THEN 0 ELSE 1 END AS user_reported
                FROM discussion_posts p
                JOIN users u ON u.id = p.user_id
                LEFT JOIN discussion_post_likes l ON l.post_id = p.id AND l.user_id = ?
                LEFT JOIN discussion_post_reports r ON r.post_id = p.id AND r.user_id = ?
                WHERE p.topic = ?
                ORDER BY p.created_at DESC LIMIT ? OFFSET ?
            """, (viewer_id, viewer_id, norm_topic, limit, offset))
        posts = [serialize_discussion_post(dict(row)) for row in c.fetchall()]
        c.execute("SELECT COUNT(*) FROM discussion_posts WHERE topic = ?", (norm_topic,))
        total = c.fetchone()[0]
        return {"status": "success", "data": {"topic": norm_topic, "category": DISCUSSION_TOPIC_TO_CATEGORY[norm_topic], "posts": posts, "total": total, "limit": limit, "offset": offset}}
    finally:
        c.close()
        conn.close()

@app.post("/discussion/posts")
async def create_discussion_post(data: DiscussionPostCreateRequest):
    norm_topic = re.sub(r"\s+", " ", data.topic or "").strip()
    norm_content = re.sub(r"\s+", " ", data.content or "").strip()
    if norm_topic not in DISCUSSION_TOPIC_TO_CATEGORY:
        raise HTTPException(400, "讨论主题不存在")
    if not norm_content:
        raise HTTPException(400, "帖子内容不能为空")
    conn = get_db_connection()
    c = conn.cursor()
    try:
        uid = get_user_id_by_username(conn, data.username)
        title = build_discussion_post_title(norm_topic, norm_content, data.title)
        c.execute("INSERT INTO discussion_posts (user_id, topic, title, content) VALUES (?, ?, ?, ?)", (uid, norm_topic, title, norm_content))
        pid = c.lastrowid
        conn.commit()
        c.execute("SELECT p.id, p.topic, p.title, p.content, p.like_count, p.report_count, p.created_at, u.username AS author FROM discussion_posts p JOIN users u ON u.id = p.user_id WHERE p.id = ?", (pid,))
        post = dict(c.fetchone())
        return {"status": "success", "message": "发布成功", "data": {"post": serialize_discussion_post(post)}}
    finally:
        c.close()
        conn.close()

@app.post("/discussion/posts/{post_id}/like")
async def toggle_discussion_post_like(post_id: int, data: DiscussionPostActionRequest):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        uid = get_user_id_by_username(conn, data.username)
        get_discussion_post_by_id(conn, post_id)
        c.execute("SELECT id FROM discussion_post_likes WHERE post_id = ? AND user_id = ?", (post_id, uid))
        if c.fetchone():
            c.execute("DELETE FROM discussion_post_likes WHERE post_id = ? AND user_id = ?", (post_id, uid))
            c.execute("UPDATE discussion_posts SET like_count = MAX(like_count - 1, 0) WHERE id = ?", (post_id,))
            action = "unliked"
            msg = "已取消点赞"
        else:
            c.execute("INSERT INTO discussion_post_likes (post_id, user_id) VALUES (?, ?)", (post_id, uid))
            c.execute("UPDATE discussion_posts SET like_count = like_count + 1 WHERE id = ?", (post_id,))
            action = "liked"
            msg = "点赞成功"
        conn.commit()
        post = fetch_discussion_post_detail(conn, post_id, uid)
        return {"status": "success", "message": msg, "data": {"action": action, "post": serialize_discussion_post(post)}}
    finally:
        c.close()
        conn.close()

@app.post("/discussion/posts/{post_id}/report")
async def report_discussion_post(post_id: int, data: DiscussionPostActionRequest):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        uid = get_user_id_by_username(conn, data.username)
        get_discussion_post_by_id(conn, post_id)
        c.execute("SELECT id FROM discussion_post_reports WHERE post_id = ? AND user_id = ?", (post_id, uid))
        if c.fetchone():
            msg = "你已举报过该帖子"
        else:
            c.execute("INSERT INTO discussion_post_reports (post_id, user_id) VALUES (?, ?)", (post_id, uid))
            c.execute("UPDATE discussion_posts SET report_count = report_count + 1 WHERE id = ?", (post_id,))
            conn.commit()
            msg = "举报已提交"
        post = fetch_discussion_post_detail(conn, post_id, uid)
        return {"status": "success", "message": msg, "data": {"post": serialize_discussion_post(post)}}
    finally:
        c.close()
        conn.close()

@app.get("/news/daily")
async def get_daily_news(limit: int = 6):
    try:
        items = fetch_daily_news(limit=max(1, min(limit, 10)))
        return {"status": "success", "data": {"news": items, "updated_at": datetime.now().isoformat()}}
    except Exception as e:
        logger.error(f"获取每日新闻失败: {str(e)}")
        return {"status": "error", "message": "获取每日新闻失败"}

@app.get("/news/recommended")
async def get_recommended_news(username: str, limit: int = 6):
    try:
        res = fetch_recommended_news_for_user(username, limit=max(1, min(limit, 10)))
        return {"status": "success", "data": {"portrait_keywords": res["portrait_keywords"], "news": res["news"], "updated_at": datetime.now().isoformat()}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取推荐新闻失败: {str(e)}")
        return {"status": "error", "message": "获取推荐新闻失败"}

@app.get("/api/overview")
def get_overview(username: str):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT identity, role FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        if not user:
            raise HTTPException(404, "用户不存在")
        db_identity = user[0] or ""
        db_role = normalize_db_role(user[1], db_identity)
        if db_role != "admin":
            raise HTTPException(403, "仅管理员可访问数据概览")
        c.execute("SELECT COUNT(*) FROM users")
        user_count = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM chat_history")
        question_count = c.fetchone()[0]
        # 模拟一些返回数据（简化）
        return {"status": "success", "data": {"stats": {"user_count": user_count, "question_count": question_count}}}
    finally:
        c.close()
        conn.close()

# ======================== /chat 接口 ========================
@app.post("/chat")
async def chat_endpoint(data: ChatRequest):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT id, identity, age_group FROM users WHERE username = ?", (data.username,))
        user = c.fetchone()
        if not user:
            raise HTTPException(404, "User not found")
        uid, user_identity, user_age_group = user[0], user[1], user[2]
        if data.conversation_id:
            conv = get_conversation_for_user(conn, uid, data.conversation_id)
        else:
            conv = create_conversation_for_user(conn, uid)
        c.execute("SELECT current_major FROM user_portraits WHERE user_id = ? ORDER BY id DESC LIMIT 1", (uid,))
        major_row = c.fetchone()
        user_major = major_row[0] if major_row else "计算机科学"
        # 获取历史画像标签
        c.execute("SELECT hidden_need, tags FROM user_portraits WHERE user_id = ? ORDER BY id DESC LIMIT 10", (uid,))
        history = c.fetchall()
        historical_tags = set()
        historical_hidden = set()
        for row in history:
            if row[1]:
                historical_tags.update(row[1].split(","))
            if row[0]:
                historical_hidden.update(row[0].split(","))
        # NLP 和风险
        explicit = nlp_pre_processing(data.message)
        rule_needs = dynamic_semantic_completion(data.message)
        risk = assess_question_risk(data.message, explicit)
        historical_context = {"historical_tags": list(historical_tags), "historical_hidden_needs": list(historical_hidden), "rule_based_needs": rule_needs}
        portrait = enhance_user_portrait(data.message, user_identity, user_age_group, historical_context, explicit)
        # 生成回复（并行）
        dual = generate_responses_dual_models(data.message, portrait, user_identity, user_age_group, user_major, explicit, risk)
        qwen_reply = dual.get("qwen", "")
        ds_reply = dual.get("deepseek", "")
        kimi_reply = dual.get("kimi", "")
        # 评分（简化，只选一个）
        # 这里为了节省篇幅，简单选 qwen 作为回复
        reply_text = qwen_reply if qwen_reply else (ds_reply if ds_reply else kimi_reply)
        # 保存聊天记录
        c.execute("""
            INSERT INTO chat_history (user_id, conversation_id, user_message, user_emotion_score, user_ideal_belief,
                user_logic_thinking, user_practice_ability, user_psychological_quality, user_hidden_needs,
                user_interest_themes, ai_reply, selected_model, qwen_score, deepseek_score, kimi_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (uid, conv["id"], data.message,
              portrait.get("emotional_state", 70), portrait.get("sentiment_score", 80),
              portrait.get("logic_score", 80), portrait.get("practice_ability", 70),
              portrait.get("psychological_quality", 75), ",".join(portrait.get("hidden_needs", [])),
              ",".join(portrait.get("interest_themes", [])), reply_text, "qwen",
              0, 0, 0))
        chat_id = c.lastrowid
        conn.commit()
        # 更新用户画像
        all_tags_list = explicit["identities"] + portrait["interest_themes"] + portrait["hidden_needs"]
        all_tags_dedup = list(dict.fromkeys(all_tags_list))
        all_needs_dedup = list(dict.fromkeys(portrait["hidden_needs"] + list(historical_hidden)))
        consolidated = consolidate_user_tags(all_tags_dedup, all_needs_dedup)
        tags_str = ",".join(consolidated["tags"][:20])
        needs_str = ",".join(consolidated["hidden_needs"])[:500]
        c.execute("SELECT id FROM user_portraits WHERE user_id = ? ORDER BY id DESC LIMIT 1", (uid,))
        existing = c.fetchone()
        if existing:
            c.execute("UPDATE user_portraits SET ideal_belief=?, logic_thinking=?, practice_ability=?, psychological_quality=?, emotional_state=?, hidden_need=?, tags=?, chat_content=? WHERE id=?",
                      (portrait["sentiment_score"], portrait["logic_score"], portrait.get("practice_ability", 70),
                       portrait.get("psychological_quality", 75), portrait.get("emotional_state", 70),
                       needs_str, tags_str, data.message, existing[0]))
        else:
            c.execute("INSERT INTO user_portraits (user_id, ideal_belief, logic_thinking, practice_ability, psychological_quality, emotional_state, hidden_need, tags, current_major, chat_content) VALUES (?,?,?,?,?,?,?,?,?,?)",
                      (uid, portrait["sentiment_score"], portrait["logic_score"], portrait.get("practice_ability", 70),
                       portrait.get("psychological_quality", 75), portrait.get("emotional_state", 70),
                       needs_str, tags_str, user_major, data.message))
        conn.commit()
        return {"status": "success", "reply": reply_text, "chat_id": chat_id, "conversation_id": conv["id"],
                "conversation": serialize_conversation(conv), "selected_model": "qwen"}
    except Exception as e:
        logger.exception("Chat endpoint error")
        return {"status": "error", "message": str(e)}
    finally:
        c.close()
        conn.close()

# ======================== 启动 ========================
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)