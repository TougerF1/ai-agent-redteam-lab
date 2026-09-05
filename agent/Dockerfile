# 靶机 agent 镜像
# 基于 python slim，安装依赖，跑多权限 agent
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先装依赖（缓存层）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝源码
COPY src/ /app/src/

# 靶机 agent 端口（仅 lab_internal 内可达）
EXPOSE 8000

# 默认启动 agent
CMD ["python", "-m", "src.main"]
