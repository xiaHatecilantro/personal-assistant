# Agent API

所有路径位于 `/api/v1/agent`，除健康检查外都需要 `Authorization: Bearer <token>`。
示例 curl 使用 Bash/Git Bash 语法；Windows PowerShell 的完整操作见 [Demo](agent-demo.md)。

## REST

| 方法 | 路径 | 成功响应 | 说明 |
| --- | --- | --- | --- |
| POST | /runs | 202 RunDetail | 提交目标；后台执行，202 不代表完成 |
| GET | /runs | 200 RunSummary[] | 当前用户 Run，按创建时间倒序 |
| GET | /runs/{id} | 200 RunDetail | 持久化状态和最终摘要 |
| GET | /runs/{id}/events?after=N | 200 AgentEvent[] | 仅 sequence>N，升序 |
| GET | /runs/{id}/approvals | 200 Approval[] | 持久化审批卡片，包括已处理记录 |
| POST | /runs/{id}/approvals/{approvalId}/decision | 200 Approval | 审批提交后异步恢复，不保证立刻完成 |
| POST | /runs/{id}/cancel | 200 RunDetail | 持久化取消意图，终态重复取消保持结果 |
| POST | /runs/{id}/resume | 200 RunDetail | 仅 interrupted 可显式恢复原线程 |

创建体仅含 `goal`：去除两端空白，长度 1–4000，拒绝额外字段。
RunDetail 包含 `id/goal/status/created_at/updated_at/thread_id/graph_version/max_steps/timeout_seconds/step_count/final_answer/error_code/error_message/started_at/finished_at`。
状态为 `queued/running/waiting_approval/completed/failed/cancelling/interrupted/cancelled`。
`thread_id`、owner、模型凭据、预算均由服务端确定，客户端不能创建或覆盖。

```bash
curl -sS -X POST "$BASE/api/v1/agent/runs" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"goal":"请查询我的待办任务"}'
curl -sS "$BASE/api/v1/agent/runs/$RUN_ID/events?after=0" \
  -H "Authorization: Bearer $TOKEN"
```

## 审批决定

Approval 包含 `id/run_id/tool_call_id/tool_name/arguments/approved_arguments/status/revision/decision/created_at/reviewed_at`。
原始 `arguments` 不覆盖；批准或编辑后在 `approved_arguments` 返回实际批准快照。
状态为 `pending/approved/rejected`；仅 pending 且 Run 待审批时可提交决定。
revision 必须使用 GET 返回的当前值，成功后加一，不应在客户端硬编码后续版本。

```json
{"decision":"approve","revision":1}
```

拒绝使用 `decision=reject`，不能携带 `edited_arguments`。
编辑参数为原参数的合并补丁，仅允许当前工具输入模型字段；服务端重新验证完整合并结果。

```json
{"decision":"edit","revision":1,"edited_arguments":{"title":"学习 Agent 评测","priority":"high"}}
```

## SSE 与重连

`GET /runs/{id}/events/stream?after=N`（别名 `/runs/{id}/stream`）使用 Bearer Header。
浏览器用 fetch 而不是把 token 放进 URL。服务器不读取 Last-Event-ID Header；客户端必须显式携带 `after`。

```bash
curl -N "$BASE/api/v1/agent/runs/$RUN_ID/events/stream?after=0" \
  -H "Authorization: Bearer $TOKEN"
```

```text
id: 1
event: run.started
data: {"schema_version":1,"run_id":"<UUID>","sequence":1,"type":"run.started","created_at":"<ISO8601>","data":{}}

event: heartbeat
data: {"run_id":"<UUID>"}
```

业务事件信封含 `schema_version=1`、`sequence>=1`、type、created_at 和 JSON data。
heartbeat 约每 15 秒发送，无持久化 sequence，不能更新客户端游标。
客户端记住最后一个成功解析的业务 sequence，断线后重新 GET 快照和 `after=N` 事件，按序号去重。
`completed/failed/cancelled` 在发送剩余事件后关闭流；待审批不会自动关闭，断开不触发取消。

## 错误和边界

| 状态码 | 含义 | 处理 |
| --- | --- | --- |
| 401 | 缺失、无效或过期 token | 登录后重试 |
| 404 | Run/审批不存在或属于他人 | 不区分存在性，不显示他人信息 |
| 409 | 非法 Run 状态、旧 revision、重复决定、恢复冲突或不支持原 Graph | 重取 Run/审批，不能盲目重发写入 |
| 422 | goal、after、决定或工具编辑参数无效 | 修改输入后重试 |
| 503 | Runtime 不就绪或正在退出 | 检查后端模型配置，读取最新持久化状态 |

特别注意：决定接口返回 503 可能表示“审批已保存，但运行暂时中断”。不能据此认为审批事务失败。
先查审批和 Run；若 Run 为 interrupted，使用 resume，不是再次提交审批。
取消只阻止后续执行，不能回滚已经提交的任务/笔记。
恢复使用原 Checkpoint，不允许 completed/failed/cancelled 重新运行；重新创建 goal 是新 Run，不是恢复。

契约依据：`backend/app/routers/agents.py`、`agent/schemas.py`、`agent/events.py`。
权限、CAS、重连及恢复的自动化证据位于 `backend/tests/agent/`，固定场景见 [评测报告](agent-evaluation.md)。
