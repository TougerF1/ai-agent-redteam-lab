# redteam 攻击侧镜像
# 集成 Garak (NVIDIA LLM红队) + PyRIT (微软 AI安全评估框架)
# 用于对靶机/模型自动化攻击测试
FROM python:3.12-slim

# 编译依赖（garak/PyRIT 需要 gcc 等编译部分 C 扩展）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /redteam

# 先装工具依赖（缓存层，加快重建）
COPY redteam-requirements.txt .
RUN pip install --no-cache-dir -r redteam-requirements.txt

# 拷贝攻击脚本
COPY scripts/ /redteam/scripts/

# 默认进入交互式 shell，供手动/自动攻击
CMD ["bash"]
