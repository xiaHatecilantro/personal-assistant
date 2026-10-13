FROM python:3.11-slim

WORKDIR /app

# 先复制依赖清单以复用镜像层；业务源码变化不会重复安装 Python 包。
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 8000

# 迁移、Checkpoint 初始化和 API 启动顺序统一由入口脚本控制。
CMD ["/app/docker-entrypoint.sh"]
