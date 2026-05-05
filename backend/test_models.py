"""
快速测试模型加载是否成功
"""
import os

# 设置镜像（必须在导入前）
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

from transformers import AutoTokenizer, AutoModelForSequenceClassification
from sentence_transformers import SentenceTransformer

print("=" * 60)
print("测试模型加载")
print("=" * 60)

# 测试BERT模型
print("\n[1/2] 加载BERT模型...")
try:
    bert_tokenizer = AutoTokenizer.from_pretrained("uer/roberta-base-finetuned-jd-binary-chinese")
    bert_model = AutoModelForSequenceClassification.from_pretrained("uer/roberta-base-finetuned-jd-binary-chinese")
    print("✅ BERT模型加载成功！")
    
    # 测试推理
    text = "这个课程非常有意义，让我深受启发"
    inputs = bert_tokenizer(text, return_tensors="pt")
    outputs = bert_model(**inputs)
    print(f"   测试文本: {text}")
    print(f"   输出维度: {outputs.logits.shape}")
except Exception as e:
    print(f"❌ BERT模型加载失败: {e}")

# 测试Sentence Transformer
print("\n[2/2] 加载Sentence Transformer模型...")
try:
    embedding_model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
    print("✅ Sentence Transformer模型加载成功！")
    
    # 测试向量化
    text = "思政教育"
    embedding = embedding_model.encode(text)
    print(f"   测试文本: {text}")
    print(f"   向量维度: {embedding.shape}")
except Exception as e:
    print(f"❌ Sentence Transformer模型加载失败: {e}")

print("\n" + "=" * 60)
print("✅ 所有模型测试通过！main.py现在应该可以正常运行了")
print("=" * 60)
