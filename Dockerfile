# 使用Python 3.10作为基础镜像
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装依赖（阿里云镜像加速）
RUN pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ && \
    pip install --no-cache-dir wsgidav cheroot supervisor -i https://mirrors.aliyun.com/pypi/simple/

# 复制项目文件
COPY . .

# 创建必要的目录
RUN mkdir -p /app/logs /app/data/chroma_db /app/knowledge/vault

# 暴露端口
EXPOSE 8000 8081

# 启动命令（supervisord 管理双进程）
CMD ["supervisord", "-c", "/app/supervisord.conf"]
