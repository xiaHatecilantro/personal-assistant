# Agent 架构

## 运行链路

```text
React AgentPage → REST 创建 Run → MySQL 提交 Run → AgentRuntime 后台任务
                                                       ↓
                                LangGraph decide → 工具 → observe → 决策循环
                                      │           │
                               PostgreSQL      MySQL 审批、业务写入、台账、事件
                               Checkpoint         │
React 时间线 ← 按 sequence 回放的 REST / SSE ←──────┘
```

HTTP 连接只负责提交或读取。断开 SSE 不会取消 Run；取消必须调用独立接口。
不在聊天 Router 中增加循环，因为执行状态、人工等待和恢复生命周期不能依附浏览器连接。
普通聊天仍是独立的一轮 SSE 对话，并不自动获得 Agent 工具权限。

## 文件职责

| 文件或目录 | 职责 |
| --- | --- |
| backend/app/main.py | 生命周期装配 Graph/Runtime，启动纠偏，关闭后台任务后释放 Checkpointer |
| backend/app/routers/agents.py | 身份与 owner 校验、Run 查询、审批 CAS、取消恢复、事件订阅 |
| backend/app/agent/state.py | 纯 JSON Graph State，不放 Session、Client、密钥等运行对象 |
| schemas.py / events.py / policies.py | HTTP 契约、版本化事件、状态迁移及审批参数 hash |
| model_gateway.py | 把供应商响应转为内部工具决策或最终回答；模型凭据来自后端 Settings |
| graph.py | 决策、只读执行、审批暂停、批准写入、观察、预算和结束节点 |
| runtime.py | Run 执行、超时、进程内任务注册、显式恢复及启动纠偏 |
| repository.py / event_recorder.py | MySQL 记录、顺序事件、稳定事件映射和公共数据脱敏 |
| tools/ | 冻结工具白名单、输入模型、owner 上下文及实际业务读写 |
| checkpoint.py | PostgreSQL Checkpointer 连接与官方 setup 初始化 |
| backend/app/agent_models.py | Run、Event、Approval、ToolExecution ORM 与唯一约束 |
| backend/evals/ | 场景数据、真实执行路径、指标、无外部 API 的 CLI |
| frontend/src/api/agents.ts / agentStream.ts | REST 调用和 fetch SSE 分块解析 |
| frontend/src/pages/AgentPage.tsx | Run 选择、持久化快照、事件去重与重连、取消和恢复入口 |
| frontend/src/components/agent/ | 输入、工具时间线、审批卡片及最终摘要 |

表中短文件名均属于 `backend/app/agent/`。这里保留模块化单体，不增加消息队列或独立 Agent 服务。

## 双库权威边界

MySQL 是用户、任务、笔记以及 Run 状态、审批、工具执行台账和公开事件的权威数据源。
PostgreSQL 仅保存 LangGraph 的执行 Checkpoint，由 Checkpointer 的 `setup()` 管理内部表。
Alembic 只管理 MySQL 业务表，不能替代 Checkpoint 初始化。

两库没有分布式事务。写工具将业务副作用、执行台账及对应事件在同一 MySQL 事务中提交。
如果事务提交后、Checkpoint 落盘前中断，恢复可能重放工具；`(run_id, tool_call_id)` 台账返回既有结果，避免第二次业务副作用。
这里保证的是同一逻辑工具调用的 effectively-once，不是所有跨系统操作的 exactly-once。
模型重新生成不同 `tool_call_id` 的另一次写请求仍需新审批，不会被语义去重。

## 审批与恢复

只读工具：`list_tasks`、`get_task`、`search_notes`、`get_note`、`lint_knowledge`。
写工具：`create_task`、`update_task`、`create_note`，全部必须人工审批。
没有 SQL、Shell、删除或任意 HTTP 工具。

审批准备节点先持久化工具、版本和参数快照，等待节点通过 `interrupt()` 暂停。
决定接口先锁 Run 再锁 Approval，以 revision CAS 防止两个标签页重复处理。
编辑参数重新通过工具输入模型验证，生成批准快照及 hash；执行只使用批准快照。
审批先提交，再用原线程的 `Command(resume=...)` 恢复，不能把审批请求体直接交给工具执行。

新 Run 使用 `write-v1`；已存 `read-v1` 仍保持原拓扑。Run 中冻结 Graph 版本、线程及执行预算。
启动时只纠偏状态，不自动重放业务；运行遗留态转为 `interrupted`，用户显式调用 resume。
待审批保持待审；审批已提交而未恢复的崩溃窗口转为中断，再由显式恢复处理。
取消先持久化意图，再辅助取消进程内任务；已提交写入不回滚。

状态迁移以 `policies.py` 为准：

```text
queued → running ⇄ waiting_approval
           │              │
           ├──→ interrupted ──显式 resume──→ running
           ├──→ completed / failed
           └──→ cancelling → cancelled
interrupted ──取消──→ cancelled
```

图示省略失败支路；`completed`、`failed`、`cancelled` 都是终态。

## 事件、安全与预算

公开事件不是 LangGraph 内部对象。信封包含 `schema_version=1`、Run ID、sequence、type、created_at 和 data。
sequence 在单个 Run 内递增且唯一；客户端按序号去重，重连携带 `after=lastSequence`。
15 秒 heartbeat 仅保持订阅，不属于持久化业务事件，不推进游标。
Agent 目前展示离散决策/工具事件，不提供真实模型逐 token 的 Agent 流式输出。

身份由 JWT 和服务端 ToolContext 确定。模型参数不能提供 owner_id、Run 身份或任意能力。
笔记与工具输出标为不可信数据，最终授权靠工具白名单、Pydantic 校验和 owner 查询，而不是只靠提示词。
事件及公共结果做敏感字段和文本脱敏；这不等于检测一切未知形式的秘密，真实凭据不得作为业务输入。

步数预算限制工具执行循环；超时限制每段活跃执行，等待人工审批不占用后台任务。
当前超时在恢复后重新计时，不是包括人工等待时间的全生命周期累计时限。

## 当前边界

- 单 backend 进程，无租约、队列或多实例调度；不能启动多个 worker 并发扫描同一 Run。
- 内存任务注册负责当前进程执行，PostgreSQL Checkpoint 与 MySQL 状态负责持久化。
- `/health/ready` 只检查 MySQL；缺模型密钥时 Runtime 不装配，读历史仍可用，执行类接口返回 503。
- 离线 Fake 评测证明确定性工程路径；真实模型质量、真实双库恢复、并发压力和生产部署仍需独立验证。
- 暂无 Token/费用预算、生产集中监控、真实多实例容灾或跨系统事务。
