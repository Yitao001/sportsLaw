# SportsLax 阿里云服务器部署指南

## 一、准备工作

### 1.1 服务器要求

- 操作系统：Ubuntu 20.04/22.04 LTS（推荐）或 CentOS 7+
- 配置：2核4G 起步（建议4核8G）
- 磁盘：至少20G 可用空间
- 开放端口：8000（或自定义端口）

### 1.2 本地准备

确保本地已：
- ✅ 初始化 Git 仓库
- ✅ 提交代码到 GitHub/Gitee

---

## 二、服务器环境配置

### 2.1 连接服务器

```bash
ssh root@your-server-ip
```

### 2.2 安装 Docker 和 Docker Compose

#### Ubuntu/Debian：

```bash
# 更新包索引
apt update && apt upgrade -y

# 安装依赖
apt install -y apt-transport-https ca-certificates curl software-properties-common

# 添加 Docker GPG 密钥
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# 添加 Docker 仓库
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

# 安装 Docker
apt update
apt install -y docker-ce docker-ce-cli containerd.io

# 安装 Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# 验证安装
docker --version
docker-compose --version
```

#### CentOS：

```bash
# 安装 Docker
yum install -y yum-utils
yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
yum install -y docker-ce docker-ce-cli containerd.io

# 启动 Docker
systemctl start docker
systemctl enable docker

# 安装 Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
```

---

## 三、部署项目

### 3.1 克隆代码

```bash
cd /opt
git clone https://github.com/your-username/sportslax.git
cd sportslax
```

或使用 Gitee：

```bash
git clone https://gitee.com/your-username/sportslax.git
```

### 3.2 配置环境变量

```bash
cp .env.example .env
nano .env
```

填入你的配置，至少配置一个 LLM API Key：

```env
MODEL_PROVIDER=tongyi
DASHSCOPE_API_KEY=sk-your-actual-key-here
```

保存退出：`Ctrl+O`，`Enter`，`Ctrl+X`

### 3.3 启动服务

```bash
docker-compose up -d
```

### 3.4 查看服务状态

```bash
# 查看容器状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

---

## 四、配置 Nginx 反向代理（可选但推荐）

### 4.1 安装 Nginx

```bash
apt install -y nginx
```

### 4.2 配置 Nginx

创建配置文件：

```bash
nano /etc/nginx/sites-available/sportslax
```

填入内容：

```nginx
server {
    listen 80;
    server_name your-domain.com;  # 替换为你的域名或服务器IP

    client_max_body_size 50M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket 支持
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### 4.3 启用配置

```bash
ln -s /etc/nginx/sites-available/sportslax /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# 测试配置
nginx -t

# 重启 Nginx
systemctl restart nginx
```

---

## 五、配置 HTTPS（可选但推荐）

### 使用 Let's Encrypt 免费证书

```bash
# 安装 Certbot
apt install -y certbot python3-certbot-nginx

# 获取证书并自动配置
certbot --nginx -d your-domain.com
```

---

## 六、阿里云安全组配置

在阿里云控制台 → 云服务器 ECS → 安全组：

| 规则方向 | 授权策略 | 端口范围 | 授权对象 | 说明 |
|---------|---------|---------|---------|------|
| 入方向 | 允许 | 80/80 | 0.0.0.0/0 | HTTP |
| 入方向 | 允许 | 443/443 | 0.0.0.0/0 | HTTPS |
| 入方向 | 允许 | 8000/8000 | 0.0.0.0/0 | 应用端口（如不用Nginx） |
| 入方向 | 允许 | 22/22 | 你的IP | SSH（建议限制IP） |

---

## 七、Obsidian 知识库同步

### 方式一：本地编辑 + Git 同步（推荐）

1. 在本地用 Obsidian 编辑 `knowledge/vault/`
2. 提交并推送 Git
3. 在服务器上拉取：

```bash
cd /opt/sportslax
git pull
docker-compose restart
```

### 方式二：直接在服务器编辑

```bash
cd /opt/sportslax/knowledge/vault
# 使用 vim/nano 编辑 .md 文件，或通过 SFTP 上传
```

### 方式三：使用 Syncthing 实时同步

在本地和服务器都安装 Syncthing，实时同步 `knowledge/vault/` 目录。

---

## 八、日常维护

### 8.1 更新代码

```bash
cd /opt/sportslax
git pull
docker-compose up -d --build
```

### 8.2 查看日志

```bash
# 实时日志
docker-compose logs -f

# 最近100行
docker-compose logs --tail=100
```

### 8.3 备份数据

```bash
# 备份知识库
tar -czf sportslax-vault-$(date +%Y%m%d).tar.gz knowledge/vault/

# 备份向量数据库
tar -czf sportslax-data-$(date +%Y%m%d).tar.gz data/
```

### 8.4 重启服务

```bash
docker-compose restart
```

### 8.5 停止服务

```bash
docker-compose down
```

---

## 九、故障排查

### 9.1 容器无法启动

```bash
# 查看容器日志
docker-compose logs sportslax

# 检查端口占用
netstat -tulpn | grep 8000
```

### 9.2 磁盘空间不足

```bash
# 清理 Docker 镜像
docker system prune -a

# 清理日志
truncate -s 0 logs/*.log
```

### 9.3 权限问题

```bash
# 修复目录权限
chown -R 1000:1000 data/ knowledge/vault/ logs/
```

---

## 十、快速检查清单

部署后确认：

- [ ] Docker 和 Docker Compose 已安装
- [ ] 容器已启动 `docker-compose ps`
- [ ] API 可访问 `http://your-ip:8000/health/lite`
- [ ] Swagger UI 正常 `http://your-ip:8000/docs`
- [ ] 知识库已挂载 `ls -la knowledge/vault/`
- [ ] 安全组已配置
- [ ] （可选）Nginx 已配置
- [ ] （可选）HTTPS 证书已配置

---

## 附录：使用 systemd 管理（替代 Docker Compose）

如果想使用 systemd 管理服务，在服务器上直接运行：

```bash
# 创建服务文件
cat > /etc/systemd/system/sportslax.service << 'EOF'
[Unit]
Description=SportsLax API Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/sportslax
Environment="PATH=/usr/local/bin:/usr/bin:/bin"
ExecStart=/usr/local/bin/docker-compose up
ExecStop=/usr/local/bin/docker-compose down
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# 启用服务
systemctl daemon-reload
systemctl enable sportslax
systemctl start sportslax

# 查看状态
systemctl status sportslax
```
