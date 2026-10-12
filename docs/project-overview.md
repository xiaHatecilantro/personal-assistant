# 个人事务助理：项目说明

更新日期：2026-10-12。面向已有全栈基础的开发者，供接手维护、学习和面试展示使用；最新验收状态见[交付记录](agent-delivery.md)。

## 1. 产品与能力

这是把任务管理、知识笔记和 AI 对话放在同一工作台的个人生产力应用。用户可管理短期、长期及每日任务，拆分子任务、计时和查看统计；维护 Markdown 笔记，用分类、领域、标签和 `[[链接]]` 组织知识，查询链接图谱和断链。

普通聊天支持 OpenAI-compatible 模型及 SSE 流式回复，可注入笔记和文件内容。文件浏览读取的是服务端 `FILE_ALLOWED_ROOTS` 白名单目录；另有文档上传解析接口。聊天当前拼接最近 20 篇笔记的各 300 字符及最多 5000 字符的文件片段，没有语义检索或向量数据库；`knowledge/query`、`compile` 仍是待配置占位能力。

Agent 工作台在此基础上增加受控执行：读取任务/笔记、检查知识链接，或提出创建任务、修改任务、创建笔记请求，由用户审批后执行。仓库中的 SeekFlow、`.agents` 等描述开发辅助流程，不属于应用业务功能。

## 2. 技术与目录导航

| 位置 | 职责 |
| --- | --- |
| `frontend/src/App.tsx`、`pages/` | React 19、TypeScript、Vite 页面路由及认证边界；`AgentPage` 展示执行时间线与审批 |
| `frontend/src/api/`、`store/` | REST/SSE 客户端；TanStack Query 缓存服务端数据，Zustand 管理会话和界面状态 |
| `backend/app/main.py`、`routers/` | FastAPI 装配及 HTTP 编排，JWT 认证、用户归属检查 |
| `backend/app/models.py`、`agent_models.py` | SQLAlchemy 业务表及 Run、Event、Approval、Execution 模型 |
| `backend/app/services/` | 文档隔离解析、聊天上下文与模型地址白名单 |
| `backend/app/agent/graph.py`、`runtime.py` | LangGraph 决策流程；后台任务生命周期、取消和恢复 |
| `backend/app/agent/tools/`、`model_gateway.py` | 工具白名单、参数校验、业务执行；OpenAI SDK 模型协议适配 |
| `backend/alembic/`、`tests/`、`evals/` | MySQL 迁移、回归及真实双库集成测试、固定场景评测 |
| `docker-compose.yml`、`frontend/nginx.conf` | 容器部署与同源 API/SSE 代理配置 |

界面采用 Ant Design、Lobe UI、Tailwind，图表采用 Recharts。后端业务数据存 MySQL 8，LangGraph Checkpoint 存 PostgreSQL 16。

## 3. 请求、执行与一致性

业务 REST 路由统一在 `/api/v1`。`POST /agent/runs` 创建 Run，详情、事件、审批决定、取消和恢复均有独立接口。普通聊天 SSE 传回复片段；Agent SSE 传持久化事件，按 Run 内 `sequence` 回放。前端携带 Bearer Token、记录游标并去重，断开订阅不取消后台运行。完整契约见 [Agent API](agent-api.md)。

一次写操作经过“模型提出工具 → 保存审批 → Graph 中断 → 用户批准/编辑/拒绝 → 原线程恢复”。用户身份由服务端提供，工具逐项限制可访问资源；审批 revision 用 CAS 防止并发或过期决定，批准参数快照及 hash 限定实际执行内容。

MySQL 是业务结果、审批、执行记录和可见事件的权威来源。业务写入、Execution 与完成事件在同一事务提交，`(run_id, tool_call_id)` 幂等记录让 Checkpoint 重放返回既有结果。PostgreSQL 负责 Graph 状态和中断位置；两库没有跨库事务，恢复必须结合 MySQL 状态核对副作用。

取消先持久化意图，节点检查后协作退出；重复取消幂等，已提交写入保留。单后端启动时将遗留活跃运行标为 `interrupted`，用户显式恢复原 Run；待审批不会自动执行。该流程由单个后台运行时管理，没有 Celery 或多 Agent 协作。

## 4. 运行与配置

使用 Python 3.11+、README 指定的 Node.js LTS 和隔离 MySQL/PostgreSQL。复制环境模板后设置 `DATABASE_URL`、`CHECKPOINT_DATABASE_URL`、`JWT_SECRET_KEY`；Agent 另需 `AGENT_MODEL_API_KEY`，可配置模型地址、名称、最大步数及超时。普通聊天模型来自界面设置，访问地址受 `LLM_ALLOWED_BASE_URLS` 限制。凭据只填环境文件，勿提交。

数据库准备完成后，在各自目录执行：

```bash
# backend
pip install -r requirements.txt
alembic upgrade head
python -m app.agent.checkpoint
python -m app.server --reload --port 8000

# frontend
npm ci
npm run dev
```

迁移管理 MySQL；Checkpoint 内部表由官方 `setup()` 初始化。没有 Agent 密钥时可使用普通业务和查看历史，Run 执行相关操作返回 503。生产模式要求强 JWT 密钥；Compose 中 Checkpoint 主机使用服务名。详见 [README](../README.md)。

## 5. 验证与现状

2026-10-12 发布前验收：后端完整回归 271 项通过，含 6 项真实双库集成和 2 项发布配置静态契约测试；前端 18 项测试、Lint 和生产构建通过；固定评测 30/30、在线 HTTP 12 项通过。HTTP 验收使用模型供应商替身，保留真实 Graph、Runtime、工具和数据库链路，证明工程行为，不证明真实模型理解能力、抗注入或成本表现。

```bash
# backend：先安装 requirements-dev.txt
ruff check app tests alembic evals
pytest -m "not integration"
python -m evals --seed 0 --output ../.run/agent-evaluation.json

# frontend
npm exec vitest run
npm run check
```

集成测试另需专用 `MYSQL_TEST_DATABASE_URL` 和 `CHECKPOINT_DATABASE_URL`，按 README 的 `m10_acceptance` 限制准备隔离库后执行 `pytest -m integration`；不要使用业务库。CI 自动覆盖双库、迁移、评测与前端门禁。

## 6. 边界与后续工作

当前仅支持单 backend 进程；多实例需要租约/心跳与恢复归属机制。`/health/ready` 仅检查 MySQL。此前 Docker Hub 超时导致完整容器构建、空环境部署及 Nginx/SSE 验收未关闭；真实模型演示和远程 CI 状态以最新交付记录为准。前端仍有大 chunk 警告；完整离线迁移 SQL 受历史迁移反射限制，应连接数据库执行迁移。

建议优先关闭部署门禁，再做真实模型评测与成本测量；随后视需求增加语义检索、上下文策略、分布式运行及前端拆包。这些是后续方向，当前未实现。

## 7. 阅读与展示顺序

先读 README 并运行任务/笔记页面；沿 `App.tsx → api → routers → models` 理解普通业务。再读[架构](agent-architecture.md)，沿 `AgentPage → agents.py → runtime.py → graph.py → tools` 跟踪一次写审批；最后结合[演示](agent-demo.md)、[评测](agent-evaluation.md)及测试理解故障路径。

面试可用“创建任务前暂停审批，编辑后只写入一次，刷新回放，进程中断后恢复”的实例解释设计；核心是权限、审计、事务与可恢复执行，而不是仅展示模型返回文本。
