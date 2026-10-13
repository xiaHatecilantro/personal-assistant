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

### Agent 工作台
- `/agent` 创建并查看 Run；事件按持久化序号回放，刷新或断线后继续读取。
- 只读工具直接执行；创建/修改任务和创建笔记必须先由当前用户审批，支持拒绝或编辑参数。
- 审批后从同一 LangGraph Checkpoint 线程恢复；业务写入按 `tool_call_id` 幂等。
- 运行中/待审批可请求取消，已中断可直接取消；取消意图持久化，重复请求幂等，已提交的业务写入不会回滚。
- 单实例启动时将遗留运行标为中断，用户可显式沿原 Checkpoint 恢复；待审批不会自动执行。当前不支持多后端实例并行扫描恢复，多实例部署需先增加租约/心跳机制。阶段边界见 `docs/Agent项目开发规划书.docx`。
- 固定 30 场景离线评测覆盖读取、审批、权限、恢复及预算边界，CI 独立检查安全门禁；不需要模型 API Key。

---

## 快速开始

### 环境要求

- Node.js 20.19+、22.13+ 或 24+ 的 LTS 版本（匹配当前 Vite/ESLint）
- Python 3.11+（CI 使用 3.11，建议独立虚拟环境）
- Docker Desktop

### 1. 启动 MySQL

```bash
docker run -d \
  --name pa-mysql \
  -e MYSQL_ROOT_PASSWORD=changeme \
  -e MYSQL_DATABASE=personal_assistant \
  -p 127.0.0.1:3307:3306 \
  mysql:8.0
```

Agent 运行状态使用独立的 PostgreSQL Checkpoint 数据库。本地开发可单独启动：

```bash
docker run -d \
  --name pa-agent-checkpoint-db \
  -e POSTGRES_USER=agent \
  -e POSTGRES_PASSWORD=changeme \
  -e POSTGRES_DB=agent_checkpoints \
  -p 127.0.0.1:5433:5432 \
  postgres:16-alpine
```

上述密码只用于本机开发，不用于生产。复制 `backend/.env.example` 后在 `backend/.env` 中配置：

```env
CHECKPOINT_DATABASE_URL=postgresql://agent:changeme@127.0.0.1:5433/agent_checkpoints
AGENT_MODEL_API_KEY=your-agent-model-key
```

LangGraph Checkpointer 的内部表由后端初始化流程调用官方 `setup()` 创建，
不通过业务数据库的 Alembic 迁移管理。

### 2. 启动后端

```bash
cd backend
cp .env.example .env
pip install -r requirements.txt
alembic upgrade head
python -m app.agent.checkpoint
python -m app.server --reload --port 8000
```

生产环境必须设置 `APP_ENV=production` 和强随机 `JWT_SECRET_KEY`。AI 对话只会访问
`LLM_ALLOWED_BASE_URLS` 中列出的地址；如需本地 Ollama，请显式把
`http://localhost:11434/v1` 加入该变量。
未配置 `AGENT_MODEL_API_KEY` 时仍可使用普通业务接口和查看 Agent 历史，创建、审批、取消和恢复 Run 返回 503。
`/health/ready` 当前只检查 MySQL，不能据此断言 Agent 模型或 PostgreSQL 已就绪。

### 3. 启动前端

```bash
cd frontend
npm ci
npm run dev
```

访问 `http://localhost:5173`

---

## 项目结构

```
├── backend/
│   ├── evals/               # 固定场景、真实路径 Runner、指标和 CLI
│   ├── tests/               # 单元、权限与显式外部集成测试
│   ├── alembic/             # MySQL 业务迁移
│   └── app/
│       ├── main.py           # FastAPI 入口
│       ├── agent/            # Agent 运行时与 PostgreSQL Checkpoint
│       ├── settings.py       # 配置解析及安全约束
│       ├── config.py         # SQLAlchemy 连接与 Session
│       ├── models.py         # SQLAlchemy 模型
│       ├── agent_models.py   # Run / Event / Approval / Execution
│       ├── auth.py           # JWT 认证
│       └── routers/          # 任务 / 笔记 / 知识库 / 文件
├── frontend/
│   └── src/
│       ├── pages/            # 业务页面与 Agent 工作台
│       ├── components/       # 布局 + 表单 + 文件树 + 任务栏
│       ├── store/            # Zustand 状态（持久化）
│       └── api/              # 请求函数 + SSE 流式
├── docker-compose.yml        # 一键部署
└── docs/                     # 项目文档
```

---

## 部署

```bash
cp .env.example .env       # 填写数据库密码、Checkpoint URL 和 JWT_SECRET_KEY
docker compose config --quiet
docker compose up -d --build
# 前端 → http://localhost
# API 文档 → http://localhost:8000/docs
```

必须替换数据库密码和默认 JWT 密钥，可用 `python -c "import secrets; print(secrets.token_urlsafe(48))"`
生成 JWT 密钥。Compose 固定 `APP_ENV=production`，默认开发密钥会被后端拒绝。
`CHECKPOINT_DATABASE_URL` 的主机必须是 `agent-checkpoint-db`，而不是宿主机的 `127.0.0.1`。
当前 Compose 把 MySQL 密码直接拼入 URL，数据库密码请使用 URL 安全字符；Checkpoint URL 密码按 URL 编码。
不配置模型密钥时部署不会自动获得 Agent 执行能力。演示步骤见 [Agent Demo](docs/agent-demo.md)。

---

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | React 19, TypeScript 6, Ant Design 6, Lobe UI, Tailwind CSS 4 |
| 动效 | Motion (Framer Motion v12) |
| 状态 | Zustand 5, TanStack Query 5 |
| 图表 | Recharts |
| 后端 | FastAPI, SQLAlchemy 2.0 |
| 数据库 | MySQL 8.0（业务数据），PostgreSQL 16（Agent Checkpoint） |
| 认证 | JWT (bcrypt + python-jose) |
| AI | OpenAI SDK 兼容（DeepSeek / OpenAI / Ollama） |
| 部署 | Docker Compose + Nginx |

## 工程化约定

- API 业务路由统一位于 `/api/v1`，健康检查使用 `/health/live` 和 `/health/ready`。
- Alembic 负责数据库结构变更；不要修改已发布迁移，应新增版本文件。
- 后端配置集中在 `backend/app/settings.py`，敏感配置只通过环境变量提供。
- Checkpoint URL 中的密码必须进行 URL 编码，并与 PostgreSQL 容器使用的原始密码一致。
- 前端服务端状态使用 TanStack Query，本地 UI 状态使用 Zustand；密码和模型 API Key
  不持久化到 `localStorage`。
- 文件解析与 LLM 上下文构造位于 `backend/app/services/`，Router 只处理 HTTP 编排。

提交前运行：

```bash
# 后端
cd backend
pip install -r requirements-dev.txt
ruff check app tests alembic evals
pytest -m "not integration"
python -m evals --seed 0 --output ../.run/agent-evaluation.json
# 真实双库测试仅在已配置的隔离测试数据库上执行
# 先迁移专用 m10_acceptance 库，再配置 MYSQL_TEST_DATABASE_URL 和 CHECKPOINT_DATABASE_URL
# MYSQL_TEST_DATABASE_URL=... CHECKPOINT_DATABASE_URL=... pytest -m integration

# 前端
cd frontend
npm exec vitest run
npm run check
```

GitHub Actions 会在专用 MySQL 8 测试库验证 Alembic 往返、并发事件序号、CAS 和写工具幂等，
在 PostgreSQL 16 上验证 Agent Checkpoint 跨连接恢复，并执行后端测试、30 场景评测、
前端测试、Lint 与生产构建。迁移测试仅接受 `m10_acceptance`，创建并清理自有 UUID 临时库；
不要把生产数据库地址传给测试。新增 `0004_mysql_fk_indexes` 为历史回滚保留外键支撑索引，
其 downgrade 刻意不删除这些索引，回退到 base 时才随业务表删除。
本地单元测试与离线评测通过不等于真实双库验证通过，交付状态见 [交付记录](docs/agent-delivery.md)。

## Agent 开发文档

- [完整项目说明](docs/project-overview.md)（[Word 版](docs/个人事务助理项目说明书.docx)）
- [架构与边界](docs/agent-architecture.md)
- [REST / SSE 契约](docs/agent-api.md)
- [演示与故障路径](docs/agent-demo.md)
- [评测基线](docs/agent-evaluation.md)

## 许可证

MIT
