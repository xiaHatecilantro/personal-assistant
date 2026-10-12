# M9 与 M10 交付记录

记录日期：2026-10-12。M9 已完成；M10 的实现、文档、质量门禁、真实双库与在线 HTTP 工程验收已完成，
完整容器部署仍阻塞，不能把 M10 总状态记为完成。真实模型演示、远程 CI 尚未验证。
本轮获得用户授权后启动隔离双库和本机测试服务，仅重启自有验收后端；未修改用户模型选择配置、
原 `.env`、既有容器或业务数据卷。随后用户明确要求提交与推送，发布检查见下文。

## 发布检查

最终后端全量回归 271 passed，含 6 项真实双库集成测试；Ruff、pip check 通过。
前端 18 项测试、Lint、TypeScript 和生产构建通过；30 场景评测门禁通过。
发布补齐 `.env.*`、测试缓存、本地数据库与 Word 锁文件的排除规则，并为 Nginx SSE 设置
HTTP/1.1、禁用响应缓冲和 300 秒读取等待窗口。两项配置静态契约测试先失败再通过；不替代容器验收。
只读候选内容扫描未发现高置信度令牌或私钥；该扫描不保证识别所有形式的敏感信息。
新增 [完整项目说明](project-overview.md) 与 Word 版，已逐页检查。
用户授权发布到 `origin` 的 `codex/m2-agent-domain` 分支；不强制推送、不直接合并 main、不创建 PR。
实际提交 SHA 与远程推送结果以 Git 记录和本次交付为准；远程 CI 不能用本地测试结果替代。

## 2026-10-12 收尾验收

| 项目 | 结果 | 证据 |
| --- | --- | --- |
| 后端全量回归 | 269 passed，1 warning；含 6 项真实集成测试，没有 skip | backend/tests；本轮 pytest 全量结果 |
| 静态检查 | Ruff 通过 | ruff check app tests alembic evals |
| 迁移回归 | upgrade head → 0003 → head → base → head 通过 | test_mysql_migrations.py |
| MySQL 并发 | 6 连接序号连续唯一；CAS 只有一名赢家；写入重放只有一条 Task/Execution/完成事件 | test_mysql_integration.py |
| PostgreSQL | Checkpoint 跨连接恢复和线程隔离 2 项通过 | test_checkpoint_integration.py；test_graph_checkpoint.py |
| HTTP 工程验收 | 12 项通过，含真实进程中断与显式恢复 | .run/m10-http-acceptance.json |
| 浏览器验收 | 注册、目标提交、编辑批准、刷新恢复、实际任务核对通过，控制台错误 0 | 隔离前端 18080，浏览器专用测试账户 |
| 确定性评测 | 30/30 通过，未审批写入 0，场景 hash 与基线一致 | .run/m10-final-evaluation.json |
| 前端测试与构建 | 上轮 18 项测试及 check 通过；本轮前端源码未修改，不重复全量构建 | 2026-10-11 记录 |
| 容器构建 | 失败，auth.docker.io 拉取基础镜像超时 | 本轮 docker compose build backend frontend |
| Word 收尾 | 规划书 v1.3 共 29 页，复盘共 25 页；目录已刷新，全部页面导出并检查 | 两份 docs/*.docx |

12 项 HTTP 检查包含：未批准不写任务、跨用户访问/决定 404、非法编辑保持待审、断开订阅不取消、
编辑后单次写入及旧 revision 409、SSE 游标重放与终态关流、终态不能恢复、拒绝无副作用、
取消可重复、读工具无需审批、待审批重启后继续原 Run、活跃进程中断后标记 interrupted 并显式恢复。
这里没有替换 Graph、Runtime、Gateway、业务工具或数据库；仅供应商 HTTP 服务返回固定工具/最终答案。
不产生模型费用，不证明真实模型理解能力、抗注入或性能。

真实回滚先复现 MySQL 1553：`0002` 删除查询索引时该索引正被 InnoDB 用于支撑外键。
新增 `0004_mysql_fk_indexes` 给 tasks/notes/raw_sources 提供独立 owner_id 索引，并同步 ORM 元数据。
已发布 `0001`～`0003` 保持不变。`0004.downgrade` 保留支撑索引，防止继续回退历史版本再次失败；
回退到 base 时随表移除，回到 0003 后再次升级会复用索引。
迁移回归还通过 4 项故障 URL 拒绝测试，禁止 database/db/init_command/host 等驱动覆盖参数，
并在执行 Alembic 前核对 UUID 临时库，避免测试误删原验收表。

本轮只删除了自己创建的 UUID 临时迁移库，以及首次失败留下的已核实空验收 schema，没有删除业务记录。
双库验收数据卷目前保留。原 `pa-mysql`、`pa-agent-checkpoint-db` 及其数据卷未启动、修改或删除。

## 验收环境与待验项

本轮专用资源为 `m10-acceptance-mysql`（13307）、`m10-acceptance-postgres`（15433），
MySQL 库 `m10_acceptance`，PostgreSQL 库 `m10_acceptance_checkpoints`。
本机 API、前端和模型替身分别监听 127.0.0.1 的 18000、18080、18081；自有进程记录在
`.run/m10-owned-processes.json`。该环境仍在运行，前端只供工程验收，不是接入真实模型的生产部署。
辅助脚本、合成验收凭据和报告均放在 Git 忽略的 `.run`，不应提交或用于生产。

仍需验证：Docker Hub 网络恢复后的完整镜像构建与空环境 Compose 部署、实际容器 healthcheck、
Nginx 同源代理/SSE、真实模型演示，以及提交代码后远程 GitHub Actions。
没有为绕过网络问题修改 Docker 全局代理、DNS、镜像源或系统网络配置。
这些门禁通过后再更新 M10 总状态；本机 HTTP 验收不替代 Nginx 或容器部署验证。

## 2026-10-11 离线验证历史

## 本次验证

| 项目 | 命令或方式 | 结果 |
| --- | --- | --- |
| 后端非集成回归 | python -m pytest tests -m "not integration" | 259 passed，2 deselected，1 warning |
| 后端静态检查 | ruff check app tests alembic evals | 通过 |
| 依赖完整性 | python -m pip check | 通过 |
| 前端测试 | npm exec vitest run | 6 文件、18 测试通过 |
| 前端 lint 与生产构建 | npm run check | 通过，有既有性能警告 |
| 30 场景评测 | python -m evals --seed 0 --output ../.run/agent-evaluation.json | 完成率 100%，未审批写入 0，审批 8/8、越权 10/10、重放 1/1 |
| 部署配置 | docker compose --env-file .env.example config --quiet | 临时提供仅用于配置检查的 JWT 值后通过，未启动容器 |
| 配置负面检查 | 空 JWT 下执行同一 config 命令 | 按预期拒绝 |
| 迁移链 | python -m alembic heads | 单一 0003_agent_runtime head |
| Agent 迁移 SQL | python -m alembic upgrade 0002_integrity_constraints:head --sql | 通过，不连接数据库 |
| 完整离线迁移 | python -m alembic upgrade head --sql | 失败，原因见下方，不记为通过 |
| Word 更新 | 保留原模板及历史内容，追加现状、指标、面试回答与证据 | 最终文件经 Word 导出全部页面并检查 |

Windows 本次使用 `backend/venv/Scripts/python.exe`；沙箱内 asyncio 初始化受限，含异步执行的测试在沙箱外运行。
假模型仅替代决策，真实 Graph/Runtime/审批/工具路径正常执行。两次安全评测假通过问题经故障注入修复并复核。
评测数据 hash、指标定义及复现命令见 [评测基线](agent-evaluation.md)。

## 2026-10-11 未关闭项快照

Docker 客户端可用，但 daemon 未运行；3307、5433、8000 没有监听。因此本次未验证：

- 真实 MySQL 全链路 upgrade/downgrade/upgrade、锁竞争和业务约束。
- 真实 PostgreSQL Checkpoint 跨连接、跨进程持久化及恢复。
- 空环境 Compose 部署、容器 healthcheck 实际执行与在线 HTTP 审批/重连/恢复演示。
- 远程 GitHub Actions 运行结果。本次仅修改流程，没有自动提交触发 CI。
- 真实模型任务完成率、模型抗注入、Token 成本、性能和并发压测。

这些项目需要操作者先启动隔离数据库或明确授权启动服务后继续验收。
`/health/ready` 只检查 MySQL；即使通过也不代表模型及 Checkpoint 执行能力可用。
当前仅支持单 backend 进程，不能用多个 worker 演示水平扩展。

## 已知限制和警告

完整离线 SQL 在 `0001_initial.upgrade()` 的 `sa.inspect(op.get_bind())` 处遇到 `MockConnection` 反射失败。
`0002_integrity_constraints` 也需要实际查询历史数据，现有迁移不能离线生成完整建库 SQL。
本次遵守“已发布迁移不修改”约定，没有为绕过校验改动历史迁移。
生成 `0003` SQL 不替代真实执行迁移；实际部署仍应使用有连接的 `alembic upgrade head`。

前端大 chunk（包括聊天页面）及构建插件耗时警告仍在；本次没有调整 chunk 阈值掩盖警告或实施范围外拆包。
后端的一条警告来自 Starlette TestClient 使用已弃用的 `anyio.abc.BlockingPortal` 别名，建议上游改用 `anyio.from_thread.BlockingPortal`。
普通回归 259 项通过；额外使用 `-W error` 定位时，该弃用警告会导致导入阶段失败，本次没有修改依赖或屏蔽警告。
两份 Word 的配套文档运行时不可用，采用独立隐藏 Word 实例只读导出 PDF，隔离的页面渲染辅助库仅安装在 `.run`，未加入运行依赖。

## 下一次部署验收

本轮双库迁移、并发和恢复门禁已经通过；下一次先恢复 Docker Hub 连接，再在独立 Compose 项目中
构建前后端镜像并运行 healthcheck、Nginx 和 [在线演示](agent-demo.md)。本轮不自动提交触发远程 CI。
按文档演示真实模型后，再核对 CI 真实结果，满足全部门禁才将规划书的 M10 总状态更新为完成。
