FROM python:3.11-slim

WORKDIR /app

# 复制依赖文件
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制后端代码
COPY backend/ .

# 设置端口（Railway 会注入 PORT 环境变量）
ENV PORT=8000

# 启动命令
CMD uvicorn main:app --host 0.0.0.0 --port $PORT