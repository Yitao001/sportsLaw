# SportsLax Docker 部署指南

## 快速开始

### 1. 准备环境

确保已安装：
- Docker
- Docker Compose

### 2. 配置环境变量

复制配置模板：

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入你的 API Key（至少配置一个 LLM 提供商）：

```env
# 选择模型提供商（siliconflow | tongyi | openai | anthropic）
MODEL_PROVIDER=siliconflow

# 填入你的 API Key
SILICONFLOW_API_KEY=sk-your-actual-key-here
# 或
DASHSCOPE_API_KEY=sk-your-actual-key-here
```

### 3. 启动服务

```bash
docker-compose up -d
```

服务将在 `http://localhost:8000` 启动。

### 4. 访问 Swagger UI

打开浏览器访问：http://localhost:8000/docs

---

## Obsidian 知识库使用

### 挂载目录说明

| 本地目录 | 容器内目录 | 用途 |
|---------|-----------|------|
| `./knowledge/vault` | `/app/knowledge/vault` | Obsidian 知识库（可编辑） |
| `./data/chroma_db` | `/app/data/chroma_db` | 向量数据库（持久化） |
| `./logs` | `/app/logs` | 日志文件 |

### 使用 Obsidian 编辑知识库

1. **打开 Obsidian**
2. 选择 "打开文件夹作为 vault"
3. 选择项目目录下的 `knowledge/vault` 文件夹
4. 开始编辑！

**同步机制**：
- 保存 `.md` 文件后，系统会在 500ms 内自动同步到向量数据库
- 也可以通过 API 手动触发：`POST /knowledge/reload`

### 知识库文档格式

每个 `.md` 文档需要包含 YAML Frontmatter：

```markdown
---
title: 文档标题
category: 分类名称
tags: [标签1, 标签2]
language: zh
---

# 正文标题

正文内容...
```

---

## 管理命令

### 查看服务状态

```bash
docker-compose ps
```

### 查看日志

```bash
# 实时日志
docker-compose logs -f

# 最近100行
docker-compose logs --tail=100
```

### 停止服务

```bash
docker-compose down
```

### 重启服务

```bash
docker-compose restart
```

### 重新构建镜像

```bash
docker-compose up -d --build
```

---

## 目录结构

```
SportsLax/
├── docker-compose.yml      # Docker Compose 配置
├── Dockerfile              # Docker 镜像构建文件
├── .env                    # 环境变量配置（需创建）
├── .env.example            # 配置模板
├── knowledge/
│   └── vault/              # Obsidian 知识库目录
│       ├── 示例-CAS仲裁上诉流程.md
│       └── 示例-WADA禁赛申诉指南.md
├── data/
│   └── chroma_db/          # 向量数据库（自动生成）
└── logs/                   # 日志目录（自动生成）
```

---

## 常见问题

### Q: 如何备份知识库？

A: 只需备份 `./knowledge/vault/` 目录即可。

### Q: 向量数据库会丢失吗？

A: 不会，`./data/chroma_db/` 已持久化，重启容器后数据保留。

### Q: 如何更新项目？

```bash
git pull
docker-compose up -d --build
```

### Q: 可以修改端口吗？

A: 可以，编辑 `docker-compose.yml` 中的 `ports` 配置：

```yaml
ports:
  - "8080:8000"  # 主机8080映射到容器8000
```

---

## 交付给客户的步骤

1. **准备交付包**：
   ```
   SportsLax/
   ├── docker-compose.yml
   ├── .env.example
   ├── knowledge/vault/（预置知识库）
   └── 部署说明.md
   ```

2. **客户操作**：
   ```bash
   # 1. 解压
   # 2. 配置 .env
   cp .env.example .env
   # 编辑 .env 填入 API Key
   
   # 3. 启动
   docker-compose up -d
   
   # 4. 用 Obsidian 打开 knowledge/vault 开始编辑
   ```

3. **知识库更新**：客户直接用 Obsidian 编辑，自动同步！
