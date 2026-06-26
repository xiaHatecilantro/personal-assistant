# 个人事务助理

> 任务管理 + 知识库 + AI 对话，三位一体的个人生产力工具。

![技术栈](https://img.shields.io/badge/React-19-61dafb?logo=react)
![技术栈](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi)
![技术栈](https://img.shields.io/badge/MySQL-8.0-4479A1?logo=mysql)
![技术栈](https://img.shields.io/badge/TypeScript-6.0-3178c6?logo=typescript)
![技术栈](https://img.shields.io/badge/Docker-ready-2496ed?logo=docker)

---

## 功能

### 任务管理
- 三种任务类型：短期任务、长期任务（可拆分子任务）、每日任务（倒计时器）
- 优先级标签 + 状态流转（待办 → 进行中 → 已完成）
- 统计看板：完成趋势折线图、状态分布

### 知识库
- Markdown 笔记，支持 `[[双向链接]]` 语法
- 分类 / 领域 / 标签三维组织，全文搜索
- 知识图谱、断链检测

### AI 对话
- SSE 流式输出，逐 token 打字机渲染
- 多模型支持（DeepSeek / OpenAI / Ollama），对话中自由切换
- 文件上下文注入：选取本地文件自动带入分析

---

## 快速开始

### 环境要求

- Node.js 18+
- Python 3.11（conda 环境 `personal-assistant`）
- Docker Desktop

### 1. 启动 MySQL

```bash
docker run -d \
  --name pa-mysql \
  -e MYSQL_ROOT_PASSWORD=root123 \
  -e MYSQL_DATABASE=personal_assistant \
  -p 3307:3306 \
  mysql:8.0
```

### 2. 启动后端

```bash
cd backend
cp .env.example .env
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

访问 `http://localhost:5173`

---

## 项目结构

```
├── backend/
│   └── app/
│       ├── main.py           # FastAPI 入口
│       ├── config.py         # 数据库配置
│       ├── models.py         # SQLAlchemy 模型
│       ├── auth.py           # JWT 认证
│       └── routers/          # 任务 / 笔记 / 知识库 / 文件
├── frontend/
│   └── src/
│       ├── pages/            # 10 个页面组件
│       ├── components/       # 布局 + 表单 + 文件树 + 任务栏
│       ├── store/            # Zustand 状态（持久化）
│       └── api/              # 请求函数 + SSE 流式
├── docker-compose.yml        # 一键部署
└── docs/                     # 项目文档
```

---

## 部署

```bash
cp .env.example .env       # 填写 DB_PASSWORD / JWT_SECRET_KEY
docker compose up -d --build
# 前端 → http://localhost
# API 文档 → http://localhost:8000/docs
```

---

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | React 19, TypeScript 6, Ant Design 6, Lobe UI, Tailwind CSS 4 |
| 动效 | Motion (Framer Motion v12) |
| 状态 | Zustand 5, TanStack Query 5 |
| 图表 | Recharts |
| 后端 | FastAPI, SQLAlchemy 2.0 |
| 数据库 | MySQL 8.0 |
| 认证 | JWT (bcrypt + python-jose) |
| AI | OpenAI SDK 兼容（DeepSeek / OpenAI / Ollama） |
| 部署 | Docker Compose + Nginx |

## 许可证

MIT
