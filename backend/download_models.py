"""
手动下载Hugging Face模型到本地
使用国内镜像：hf-mirror.com
"""
import os

# 设置镜像
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

from transformers import AutoTokenizer, AutoModelForSequenceClassification
from sentence_transformers import SentenceTransformer

print("=" * 60)
print("开始下载模型（使用hf-mirror.com镜像）")
print("=" * 60)

# 1. 下载BERT中文情感分析模型
print("\n[1/2] 下载BERT情感分析模型...")
try:
    model_name = "uer/roberta-base-finetuned-jd-binary-chinese"
    print(f"模型: {model_name}")
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(model_name)
    print("✅ BERT模型下载成功！")
except Exception as e:
    print(f"❌ BERT模型下载失败: {e}")

# 2. 下载Sentence Transformer向量化模型
print("\n[2/2] 下载Sentence Transformer模型...")
try:
    model_name = "sentence-transformers/all-MiniLM-L6-v2"
    print(f"模型: {model_name}")
    embedding_model = SentenceTransformer(model_name)
    print("✅ Sentence Transformer模型下载成功！")
except Exception as e:
    print(f"❌ Sentence Transformer模型下载失败: {e}")

print("\n" + "=" * 60)
print("所有模型下载完成！")
print("=" * 60)
print("\n缓存位置:")
print(f"  Windows: {os.path.expanduser('~')}/.cache/huggingface")
print(f"  当前目录: {os.getcwd()}/.cache")
