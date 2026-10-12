# PCR 草案：M6 Runtime 审批暂停与 M7 取消入口

状态：已获用户确认（2026-10-09）；按本 PCR 实施并同步《Agent 项目开发规划书》的版本和变更记录。

## 原因

M6-03/04/09 规定在 Graph 中使用 `interrupt()`，但 M5 Runtime 当前把每次 `ainvoke()` 返回都当作终态。若直接按原步骤接入审批，Run 会在等待人工决定时被错误标为 `completed`，审批后也无法恢复。M7-10 要取消按钮，而取消接口按规划排在 M8-01/02。

## 建议变更与受影响步骤

在 M6-04 后增加 M6-04A：`backend/app/agent/runtime.py`、`backend/tests/agent/test_runtime.py` 识别 Graph 中断，记录 `waiting_approval`，以同一 `thread_id` 调度 `Command(resume=...)`；验证暂停不变完成、决定后能继续。

在 M6-09 后增加 M6-09A：`backend/app/agent/event_recorder.py`、`backend/tests/agent/test_event_recorder.py` 只投影新观察，避免恢复后重复事件；验证 `sequence` 连续且同一工具调用不重复展示。

M6-09 接入写 Graph 时增加 `write-v1`，新 Run 使用新版本；已持久化的 `read-v1` 仍由旧 Graph 编译并执行。装配入口需同步更新 `backend/app/main.py` 与 `backend/app/routers/agents.py`，验证旧 Run 的 Graph 版本不被静默替换。

M6-05/06 的审批接口增加 owner-scoped 审批查询，供 M7 刷新后读取快照。M7-10 的取消按钮在 M7 阶段明确禁用并说明 M8 接通；不提前执行 M8 的取消逻辑。

M6-06 的 `edit` 必须使用写工具输入模型校验，而原规划把写工具模型放在后续 M6-07/08。将 M6-07/08 中的输入模型定义提前作为 M6-06 的依赖，业务写入仍按原 M6-07/08 顺序接入。

## 文件、数据与 API 兼容性

保持四张 Agent 表结构不变。新增审批查询/决定端点和 `approval.required`、`approval.resolved` 事件；现有 Run/Event 接口保持兼容。SSE 增加规划书路径 `/runs/{id}/stream` 作为现有 `/runs/{id}/events/stream` 的别名。

## 风险与替代方案

风险：MySQL 审批事务与 PostgreSQL Checkpoint 无跨库原子提交；M6 保证业务效果幂等，进程崩溃后的自动协调仍按 M8 实现。替代方案为不接入 Runtime，仅演示审批 UI，但无法通过 M6 门禁，因此不采用。

## 新验收标准

1. 未批准时 Task/Note 无写入；Run 停在 `waiting_approval`，刷新后审批可查。
2. approve/reject/edit 均经 owner、revision 和参数校验；同一决定的重复请求返回 409。
3. 业务提交后、Checkpoint 前重放时，每个 `tool_call_id` 仅有一条业务对象与一条执行记录。
4. 审批恢复后事件不重复；后端全量测试、Ruff 与前端测试/构建通过。
