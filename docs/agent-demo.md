# Agent 演示手册

## 前置条件

先按 README 配置 MySQL、PostgreSQL、业务迁移和 Checkpoint 初始化，并由操作者启动后端及前端。
必须配置有效的 `AGENT_MODEL_API_KEY` 和允许的模型地址；未配置时执行接口返回 503。
Compose 访问 `http://localhost`，本地开发前端访问 `http://localhost:5173`，API 为 `http://localhost:8000`。
不要用生产账户或真实敏感资料演示。以下操作会创建测试用户和任务。

真实模型行为不保证每次相同：演示观察完整链路，确定性验收使用 `python -m evals`。
2026-10-12 已在隔离 MySQL/PostgreSQL 与本机生产 API 上验证以下 HTTP 路径；模型供应商
使用本地确定性 HTTP 替身，不代表真实模型演示。容器空环境部署仍受 Docker Hub 超时阻塞。
本轮验证细节见 [交付记录](agent-delivery.md)，操作者可按下文另行复现真实模型演示。

## 注册并提交目标

以下为 PowerShell 7 示例，用户名每次生成，避免已注册冲突。

```powershell
$apiBase = 'http://localhost:8000'
$demoUser = 'agent-demo-' + [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
$registration = Invoke-RestMethod -Method Post -Uri "$apiBase/api/v1/auth/register" `
    -ContentType 'application/json' -Body (@{username=$demoUser;password='Demo-pass-2026'} | ConvertTo-Json)
$authHeaders = @{Authorization='Bearer ' + $registration.token}
$demoRun = Invoke-RestMethod -Method Post -Uri "$apiBase/api/v1/agent/runs" `
    -Headers $authHeaders -ContentType 'application/json' `
    -Body (@{goal='请调用 create_task 创建短期任务，标题为学习 Agent 评测，优先级 medium；创建后结束。'} | ConvertTo-Json)
$runId = $demoRun.id
$demoRun
```

在前端用该账号登录，打开 `/agent` 选择 Run，观察工具建议、审批卡片及状态。
等待 `waiting_approval`；模型可能先读取资料，也可能返回问题，若未建议写入则查看事件和最终结果，而不是绕过审批。
待审时任务尚未创建，可在任务页面验证。下一段在准备好审批后手工执行。

## 编辑并批准

```powershell
$approvals = Invoke-RestMethod -Uri "$apiBase/api/v1/agent/runs/$runId/approvals" -Headers $authHeaders
$pending = $approvals | Where-Object status -eq 'pending' | Select-Object -First 1
if ($null -eq $pending) { throw '尚无待处理审批，请检查 Run 状态和事件。' }
$decision = @{decision='edit';revision=$pending.revision;edited_arguments=@{title='学习 Agent 评测并记录结果';priority='high'}}
Invoke-RestMethod -Method Post -Uri "$apiBase/api/v1/agent/runs/$runId/approvals/$($pending.id)/decision" `
    -Headers $authHeaders -ContentType 'application/json' -Body ($decision | ConvertTo-Json -Depth 5)
```

观察状态恢复 running 后进入 completed，任务标题和优先级应等于批准后的参数。
在前端“任务”页面核对只新增一条；刷新工作台仍能看到最终摘要。
对同一审批再次提交旧 revision 应得到 409，而不是创建第二条任务。
拒绝路径请新建 Run，在新审批提交 `decision=reject`，该工具不得产生业务副作用。

## 事件重连

```powershell
$history = @(Invoke-RestMethod -Uri "$apiBase/api/v1/agent/runs/$runId/events?after=0" -Headers $authHeaders)
$history | Select-Object sequence,type
$lastSequence = if ($history.Count) { ($history | Measure-Object sequence -Maximum).Maximum } else { 0 }
curl.exe -N -H "Authorization: Bearer $($registration.token)" `
    "$apiBase/api/v1/agent/runs/$runId/events/stream?after=$lastSequence"
```

终态若没有更多事件，流立即结束是正常行为。运行中或待审批时可 Ctrl+C 中断订阅，再携带同一游标连接。
浏览器切离页面或关闭标签页也不等于取消；返回后从快照与事件恢复时间线。

## 取消和进程中断恢复

另建一个待审批 Run，不处理审批，点击取消或调用 POST `/runs/{id}/cancel`。
Run 应最终 cancelled，待审批工具不得执行；再次取消保持终态。

重启演示仅由操作者在明确接受中断后执行，不能对生产环境操作：

1. 待审批时重启单 backend，重新查询审批仍为 pending，批准后继续原线程。
2. 活跃执行期间中断单 backend，再启动后应出现 interrupted，不自动重放。
3. GET 最新 Run 确认为 interrupted，再 POST `/runs/{id}/resume`；沿原线程执行。
4. 若 Checkpoint 已到 END，恢复仅补齐结果；若仍有 pending 审批，重新进入 waiting_approval。

不要直接编辑数据库来模拟崩溃，不要新建同一 goal 假装恢复。
边界自动测试：`test_restart_recovery.py`；离线场景 `recovery-new-runtime-waiting`、`recovery-decision-committed`。

## 失败演示和核对

| 情况 | 预期 | 复现方式 |
| --- | --- | --- |
| 跨用户读取 Run/审批/事件或提交决定 | 404，没有数据泄露或副作用 | 注册第二个测试用户，使用其 token 请求第一个用户的 Run |
| 审批编辑非法参数 | 422，审批仍可重新处理 | 新建待审 Run，edit 中增加 owner_id 等禁止字段 |
| 过期 revision 或重复决定 | 409，不重复写入 | 对同一审批重复第一次请求体 |
| 非 interrupted 运行调用 resume | 409，不从头启动 | 对 completed Run POST resume |
| 未配置模型 Key | 执行类接口 503，历史可读 | 单独未配置 Key 的环境验证，不能在线删除正在使用的凭据 |
| 步数达到上限 | failed，error_code 可查询 | 离线场景 budget-step-limit，避免让真实模型无限循环 |
| 无白名单工具或 owner 参数注入 | 受控工具失败或参数拒绝 | 离线 injection-unknown-tool / injection-owner-argument |

单个工具失败后模型仍可能继续并完成 Run，应以工具观察和数据库副作用判定安全，不只看 Run 是否 completed。
审批保存后调度失败的 503 路径，先读审批和 interrupted 状态，再显式 resume。

## 演示留证

保留 Run ID、审批原始/批准参数、事件 sequence、最终任务以及 `.run/agent-evaluation.json`。
录屏应遮挡 Bearer token、模型 Key 和私人笔记。面试展示以下关系即可：
“建议写入但未执行 → 人工编辑批准 → 按批准参数写一次 → 刷新重放 → 独立取消/恢复”。
不要把真实模型偶然一次成功当作完成率基线，也不要把离线内存 Checkpoint 测试当成已完成 PostgreSQL 容灾验收。
