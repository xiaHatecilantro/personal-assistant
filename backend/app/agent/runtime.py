"""Agent 后台运行时：管理独立于 HTTP/SSE 连接的进程内执行任务。"""

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime, timezone
from typing import Any, Protocol

from langgraph.types import Command
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.event_recorder import record_graph_output, redact_public_value
from app.agent.graph import RunCancellationRequested, build_graph_config
from app.agent.policies import InvalidRunTransition, ensure_run_transition
from app.agent.repository import append_event
from app.agent.schemas import RunStatus
from app.agent.state import AgentState
from app.agent_models import AgentApproval, AgentRun


READ_GRAPH_VERSION = "read-v1"
WRITE_GRAPH_VERSION = "write-v1"
DEFAULT_GRAPH_VERSION = WRITE_GRAPH_VERSION


class AgentGraph(Protocol):
    async def ainvoke(
        self,
        initial_state: AgentState | Command | None,
        *,
        config: Mapping[str, Any],
    ) -> AgentState: ...

    async def aget_state(self, config: Mapping[str, Any]) -> Any: ...


class DuplicateRunError(RuntimeError):
    """同一进程内已有相同 run_id 的活跃执行。"""


class RuntimePreparationError(RuntimeError):
    """持久化运行元数据无法安全解析为本进程可执行配置。"""

    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.public_message = message


class RunNotStartableError(RuntimeError):
    """Run 不存在或已不处于 queued；不得覆盖其当前状态。"""


class RuntimeShuttingDownError(RuntimeError):
    """应用正在关闭，运行时不再接受新的后台任务。"""


class RunTaskRegistry:
    """保存强引用，避免后台任务被回收，并阻止单进程内重复调度。"""

    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._accepting = True

    def start(
        self,
        run_id: str,
        operation_factory: Callable[[], Awaitable[None]],
    ) -> asyncio.Task[None]:
        if not self._accepting:
            raise RuntimeShuttingDownError("agent runtime is shutting down")
        if self.is_running(run_id):
            raise DuplicateRunError(f"run {run_id!r} is already running")

        task = asyncio.create_task(operation_factory(), name=f"agent-run:{run_id}")
        self._tasks[run_id] = task
        task.add_done_callback(lambda completed: self._discard(run_id, completed))
        return task

    def is_running(self, run_id: str) -> bool:
        task = self._tasks.get(run_id)
        return task is not None and not task.done()

    def cancel(self, run_id: str) -> bool:
        task = self._tasks.get(run_id)
        if task is None or task.done():
            return False
        # HTTP 同步路由可能在线程池调用；Task.cancel 必须调度回任务所属事件循环。
        task.get_loop().call_soon_threadsafe(task.cancel)
        return True

    async def shutdown(self) -> None:
        """停止接收任务，并等待所有活跃任务完成取消清理。"""
        self._accepting = False
        tasks = [task for task in self._tasks.values() if not task.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def _discard(self, run_id: str, completed: asyncio.Task[None]) -> None:
        # 仅清理由本次启动登记的 task，避免未来重新调度后被旧回调误删。
        if self._tasks.get(run_id) is completed:
            self._tasks.pop(run_id, None)


class AgentRuntime:
    """按 Run 中冻结的 graph_version 调度执行，并用短事务持久化运行事实。"""

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        graphs: Mapping[str, AgentGraph],
    ) -> None:
        self._session_factory = session_factory
        self._graphs = dict(graphs)
        self._tasks = RunTaskRegistry()

    def start(self, run_id: str) -> asyncio.Task[None]:
        return self._tasks.start(run_id, lambda: self._execute(run_id))

    def resume(self, run_id: str) -> asyncio.Task[None]:
        """审批提交后调度同一 Checkpoint 线程；跨进程重复恢复由 Run 状态拦截。"""
        return self._tasks.start(run_id, lambda: self._resume(run_id))

    def resume_interrupted(self, run_id: str) -> asyncio.Task[None]:
        """显式恢复原 Checkpoint；只允许一次 CAS 后启动后台任务。"""
        graph, max_steps, timeout_seconds = self._mark_recovery_started(run_id)
        try:
            return self._tasks.start(
                run_id,
                lambda: self._recover(run_id, graph, max_steps, timeout_seconds),
            )
        except (DuplicateRunError, RuntimeShuttingDownError):
            self._mark_interrupted(
                run_id,
                error_code="runtime_unavailable",
                error_message="运行时未能调度恢复",
            )
            raise

    def reconcile_startup(self) -> None:
        """单实例启动纠偏；多实例部署须先引入租约，不能并发扫描活跃 Run。"""
        with self._session_factory() as session:
            stale_runs = session.scalars(
                select(AgentRun).where(
                    AgentRun.status.in_((RunStatus.RUNNING.value, RunStatus.CANCELLING.value))
                ).with_for_update()
            ).all()
            for run in stale_runs:
                if run.status == RunStatus.CANCELLING.value and self._finish_cancelled(session, run):
                    continue
                if run.status != RunStatus.RUNNING.value:
                    continue
                if run.cancel_requested_at is not None:
                    ensure_run_transition(RunStatus.RUNNING, RunStatus.CANCELLING)
                    run.status = RunStatus.CANCELLING.value
                    self._finish_cancelled(session, run)
                    continue
                ensure_run_transition(RunStatus.RUNNING, RunStatus.INTERRUPTED)
                run.status = RunStatus.INTERRUPTED.value
                run.error_code = "process_restart"
                run.error_message = "上次进程退出后，Agent 运行已中断"
                append_event(
                    session, run_id=run.id, event_type="run.interrupted",
                    payload_json={"error_code": run.error_code, "message": run.error_message},
                )
            # 决定可能已提交但进程尚未调度 Command；无 pending 审批时显式恢复它。
            waiting_runs = session.scalars(
                select(AgentRun).where(
                    AgentRun.status == RunStatus.WAITING_APPROVAL.value
                ).with_for_update()
            ).all()
            for run in waiting_runs:
                pending = session.scalar(select(AgentApproval.id).where(
                    AgentApproval.run_id == run.id, AgentApproval.status == "pending"
                ).limit(1))
                resolved = session.scalar(select(AgentApproval.id).where(
                    AgentApproval.run_id == run.id,
                    AgentApproval.status.in_(("approved", "rejected")),
                ).limit(1))
                if pending is not None or resolved is None:
                    continue
                ensure_run_transition(RunStatus.WAITING_APPROVAL, RunStatus.INTERRUPTED)
                run.status = RunStatus.INTERRUPTED.value
                run.error_code = "approval_resume_interrupted"
                run.error_message = "审批已保存，请手动恢复运行"
                append_event(
                    session, run_id=run.id, event_type="run.interrupted",
                    payload_json={"error_code": run.error_code, "message": run.error_message},
                )
            session.commit()

    def is_running(self, run_id: str) -> bool:
        return self._tasks.is_running(run_id)

    def request_cancel(self, run_id: str) -> None:
        """数据库先记录取消意图；task.cancel 只负责加速当前进程的协作退出。"""
        if not self._tasks.cancel(run_id):
            self._finalize_cancelled(run_id)

    async def shutdown(self) -> None:
        """关闭 Runtime，保证 Checkpointer 释放前活跃任务已停止。"""
        await self._tasks.shutdown()

    async def _execute(self, run_id: str) -> None:
        try:
            graph, initial_state, max_steps, timeout_seconds = self._mark_started(run_id)
        except RunNotStartableError:
            self._finalize_cancelled(run_id)
            return
        except RuntimePreparationError as exc:
            self._mark_failed(run_id, exc.error_code, exc.public_message)
            return

        try:
            result = await asyncio.wait_for(
                graph.ainvoke(
                    initial_state,
                    config=build_graph_config(run_id=run_id, max_steps=max_steps),
                ),
                timeout=timeout_seconds,
            )
        except asyncio.CancelledError:
            self._mark_interrupted(run_id)
            raise
        except RunCancellationRequested:
            self._finalize_cancelled(run_id)
        except TimeoutError:
            self._mark_failed(run_id, "run_timeout", "Agent 运行超过总时间限制")
        except Exception:
            # 供应商异常可能含密钥、URL 或请求内容；M5 先只持久化稳定的公共错误。
            self._mark_failed(run_id, "model_error", "Agent 模型调用失败")
        else:
            try:
                if result.get("__interrupt__"):
                    self._mark_waiting(run_id, result)
                else:
                    self._persist_result(run_id, result)
            except InvalidRunTransition:
                # 终态可能被并发控制路径先写入；不得用迟到结果覆盖它。
                self._finalize_cancelled(run_id)
                return
            except (AttributeError, TypeError, ValueError):
                self._mark_failed(
                    run_id,
                    "invalid_graph_output",
                    "Agent 运行结果不符合持久化契约",
                )

    async def _resume(self, run_id: str) -> None:
        try:
            graph, max_steps, timeout_seconds = self._load_resume_target(run_id)
            config = build_graph_config(run_id=run_id, max_steps=max_steps)
            try:
                snapshot = await graph.aget_state(config)
            except asyncio.CancelledError:
                self._mark_interrupted(run_id)
                raise
            except Exception:
                # Checkpointer 可能包含连接口令；只记录可公开的中断原因，留给 M8 恢复。
                self._mark_interrupted(
                    run_id,
                    error_code="checkpoint_unavailable",
                    error_message="审批 Checkpoint 暂不可用",
                )
                return
            call = snapshot.values.get("pending_tool_call") if snapshot else None
            approval_id = call.get("approval_id") if isinstance(call, dict) else None
            if not isinstance(approval_id, str):
                raise RuntimePreparationError("invalid_checkpoint", "审批 Checkpoint 不可恢复")
            self._mark_resumed(run_id, approval_id)
        except RunNotStartableError:
            self._finalize_cancelled(run_id)
            return
        except RuntimePreparationError as exc:
            self._mark_failed(run_id, exc.error_code, exc.public_message)
            return
        try:
            result = await asyncio.wait_for(
                graph.ainvoke(Command(resume={"approval_id": approval_id}), config=config),
                timeout=timeout_seconds,
            )
        except asyncio.CancelledError:
            self._mark_interrupted(run_id)
            raise
        except RunCancellationRequested:
            self._finalize_cancelled(run_id)
        except TimeoutError:
            self._mark_failed(run_id, "run_timeout", "Agent 运行超过总时间限制")
        except Exception:
            self._mark_failed(run_id, "model_error", "Agent 模型调用失败")
        else:
            try:
                if result.get("__interrupt__"):
                    self._mark_waiting(run_id, result)
                else:
                    self._persist_result(run_id, result)
            except InvalidRunTransition:
                self._finalize_cancelled(run_id)
                return
            except (AttributeError, TypeError, ValueError):
                self._mark_failed(
                    run_id, "invalid_graph_output", "Agent 运行结果不符合持久化契约"
                )

    async def _recover(
        self, run_id: str, graph: AgentGraph, max_steps: int, timeout_seconds: int
    ) -> None:
        """只读取原线程快照；绝不从 goal 重新执行或绕过 pending 审批。"""
        config = build_graph_config(run_id=run_id, max_steps=max_steps)
        try:
            snapshot = await graph.aget_state(config)
            values = getattr(snapshot, "values", None)
            if not isinstance(values, dict) or not values or values.get("run_id", run_id) != run_id:
                raise RuntimePreparationError("invalid_checkpoint", "Agent Checkpoint 不可恢复")
            interrupted = any(
                getattr(task, "interrupts", ()) for task in getattr(snapshot, "tasks", ())
            )
            if interrupted:
                call = values.get("pending_tool_call")
                approval_id = call.get("approval_id") if isinstance(call, dict) else None
                if not isinstance(approval_id, str):
                    raise RuntimePreparationError("invalid_checkpoint", "审批 Checkpoint 不可恢复")
                with self._session_factory() as session:
                    approval = session.scalar(select(AgentApproval).where(
                        AgentApproval.id == approval_id, AgentApproval.run_id == run_id
                    ))
                    approval_status = approval.status if approval is not None else None
                if approval_status == "pending":
                    self._mark_waiting(run_id, values)
                    return
                if approval_status not in ("approved", "rejected"):
                    raise RuntimePreparationError("invalid_checkpoint", "审批快照不可恢复")
                graph_input: AgentState | Command | None = Command(
                    resume={"approval_id": approval_id}
                )
            elif getattr(snapshot, "next", ()):
                graph_input = None
            else:
                self._persist_result(run_id, values)
                return

            result = await asyncio.wait_for(
                graph.ainvoke(graph_input, config=config), timeout=timeout_seconds
            )
        except asyncio.CancelledError:
            self._mark_interrupted(run_id)
            raise
        except RunCancellationRequested:
            self._finalize_cancelled(run_id)
            return
        except RuntimePreparationError as exc:
            self._mark_interrupted(
                run_id, error_code=exc.error_code, error_message=exc.public_message
            )
            return
        except TimeoutError:
            self._mark_failed(run_id, "run_timeout", "Agent 运行超过总时间限制")
            return
        except Exception:
            self._mark_interrupted(
                run_id, error_code="checkpoint_unavailable",
                error_message="Agent Checkpoint 暂不可用",
            )
            return
        try:
            if result.get("__interrupt__"):
                self._mark_waiting(run_id, result)
            else:
                self._persist_result(run_id, result)
        except InvalidRunTransition:
            self._finalize_cancelled(run_id)
        except (AttributeError, TypeError, ValueError):
            self._mark_failed(run_id, "invalid_graph_output", "Agent 运行结果不符合持久化契约")

    def _mark_recovery_started(self, run_id: str) -> tuple[AgentGraph, int, int]:
        with self._session_factory() as session:
            run = session.scalar(select(AgentRun).where(AgentRun.id == run_id).with_for_update())
            if run is None or run.status != RunStatus.INTERRUPTED.value or run.cancel_requested_at:
                raise RunNotStartableError(f"run {run_id!r} is not recoverable")
            if run.thread_id != run_id:
                raise RuntimePreparationError(
                    "invalid_thread_identity", "Run 的线程标识与服务端运行标识不一致"
                )
            graph = self._graphs.get(run.graph_version)
            if graph is None:
                raise RuntimePreparationError(
                    "unsupported_graph_version", "Run 引用的 Graph 版本当前不可用"
                )
            ensure_run_transition(RunStatus.INTERRUPTED, RunStatus.RUNNING)
            run.status = RunStatus.RUNNING.value
            run.error_code = None
            run.error_message = None
            max_steps, timeout_seconds = run.max_steps, run.timeout_seconds
            session.commit()
            return graph, max_steps, timeout_seconds

    def _load_resume_target(self, run_id: str) -> tuple[AgentGraph, int, int]:
        with self._session_factory() as session:
            run = session.get(AgentRun, run_id)
            if run is None or run.status != RunStatus.WAITING_APPROVAL.value:
                raise RunNotStartableError(f"run {run_id!r} is not waiting for approval")
            if run.thread_id != run_id:
                raise RuntimePreparationError(
                    "invalid_thread_identity", "Run 的线程标识与服务端运行标识不一致"
                )
            graph = self._graphs.get(run.graph_version)
            if graph is None:
                raise RuntimePreparationError(
                    "unsupported_graph_version", "Run 引用的 Graph 版本当前不可用"
                )
            return graph, run.max_steps, run.timeout_seconds

    def _mark_resumed(self, run_id: str, approval_id: str) -> None:
        with self._session_factory() as session:
            run = session.scalar(select(AgentRun).where(AgentRun.id == run_id).with_for_update())
            if run is None or run.status != RunStatus.WAITING_APPROVAL.value:
                raise RunNotStartableError(f"run {run_id!r} is not waiting for approval")
            approval = session.scalar(
                select(AgentApproval).where(
                    AgentApproval.id == approval_id,
                    AgentApproval.run_id == run_id,
                    AgentApproval.status.in_(("approved", "rejected")),
                ).with_for_update()
            )
            if approval is None:
                raise RunNotStartableError("approval has not been resolved")
            ensure_run_transition(RunStatus.WAITING_APPROVAL, RunStatus.RUNNING)
            run.status = RunStatus.RUNNING.value
            session.commit()

    def _mark_waiting(self, run_id: str, result: AgentState) -> None:
        call = result.get("pending_tool_call")
        approval_id = call.get("approval_id") if isinstance(call, dict) else None
        if not isinstance(approval_id, str):
            raise ValueError("interrupted graph has no approval identity")
        with self._session_factory() as session:
            run = session.scalar(select(AgentRun).where(AgentRun.id == run_id).with_for_update())
            if run is None:
                raise LookupError(f"run {run_id!r} does not exist")
            if self._finish_cancelled(session, run):
                session.commit()
                return
            approval = session.scalar(
                select(AgentApproval).where(
                    AgentApproval.id == approval_id,
                    AgentApproval.run_id == run_id,
                    AgentApproval.status == "pending",
                )
            )
            if approval is None:
                raise ValueError("interrupted graph has no pending approval")
            ensure_run_transition(RunStatus(run.status), RunStatus.WAITING_APPROVAL)
            run.step_count = result.get("step_count", run.step_count)
            run.status = RunStatus.WAITING_APPROVAL.value
            session.commit()

    def _mark_started(self, run_id: str) -> tuple[AgentGraph, AgentState, int, int]:
        with self._session_factory() as session:
            run = session.get(AgentRun, run_id)
            if run is None:
                raise RunNotStartableError(f"run {run_id!r} does not exist")
            if run.status != RunStatus.QUEUED.value:
                raise RunNotStartableError(f"run {run_id!r} is not queued")
            ensure_run_transition(RunStatus.QUEUED, RunStatus.RUNNING)
            now = _utcnow_naive()
            run.status = RunStatus.RUNNING.value
            run.started_at = now
            append_event(
                session,
                run_id=run.id,
                event_type="run.started",
                payload_json={},
            )
            initial_state: AgentState = {
                "run_id": run.id,
                "owner_id": run.owner_id,
                "goal": run.goal,
                "step_count": 0,
                "plan": [],
                "messages": [],
                "pending_tool_call": None,
                "observations": [],
                "final_answer": None,
                "error": None,
            }
            thread_id = run.thread_id
            graph_version = run.graph_version
            max_steps = run.max_steps
            timeout_seconds = run.timeout_seconds
            session.commit()

        if thread_id != run_id:
            raise RuntimePreparationError(
                "invalid_thread_identity",
                "Run 的线程标识与服务端运行标识不一致",
            )
        graph = self._graphs.get(graph_version)
        if graph is None:
            raise RuntimePreparationError(
                "unsupported_graph_version",
                "Run 引用的 Graph 版本当前不可用",
            )
        return graph, initial_state, max_steps, timeout_seconds

    def _mark_interrupted(
        self,
        run_id: str,
        *,
        error_code: str = "runtime_shutdown",
        error_message: str = "应用关闭，Agent 运行已中断",
    ) -> None:
        with self._session_factory() as session:
            run = session.scalar(select(AgentRun).where(AgentRun.id == run_id).with_for_update())
            if run is not None and self._finish_cancelled(session, run):
                session.commit()
                return
            if run is None or run.status not in (
                RunStatus.RUNNING.value, RunStatus.WAITING_APPROVAL.value
            ):
                return
            ensure_run_transition(RunStatus(run.status), RunStatus.INTERRUPTED)
            run.status = RunStatus.INTERRUPTED.value
            run.error_code = error_code
            run.error_message = redact_public_value(error_message)
            append_event(
                session,
                run_id=run.id,
                event_type="run.interrupted",
                payload_json={
                    "error_code": run.error_code,
                    "message": run.error_message,
                },
            )
            session.commit()

    def _persist_result(self, run_id: str, result: AgentState) -> None:
        with self._session_factory() as session:
            run = session.scalar(select(AgentRun).where(AgentRun.id == run_id).with_for_update())
            if run is None:
                raise LookupError(f"run {run_id!r} does not exist")
            if self._finish_cancelled(session, run):
                session.commit()
                return
            run.step_count = result.get("step_count", 0)
            run.final_answer = redact_public_value(result.get("final_answer"))
            graph_error = result.get("error")
            if graph_error is None:
                ensure_run_transition(RunStatus(run.status), RunStatus.COMPLETED)
                run.status = RunStatus.COMPLETED.value
            else:
                error_code = graph_error.get("code")
                error_message = graph_error.get("message")
                if not isinstance(error_code, str) or not isinstance(error_message, str):
                    raise ValueError("graph error must contain string code and message")
                ensure_run_transition(RunStatus(run.status), RunStatus.FAILED)
                run.status = RunStatus.FAILED.value
                run.error_code = error_code
                run.error_message = redact_public_value(error_message)
            run.finished_at = _utcnow_naive()
            record_graph_output(session, run_id=run.id, output=result)
            session.commit()

    def _mark_failed(self, run_id: str, error_code: str, error_message: str) -> None:
        with self._session_factory() as session:
            run = session.scalar(select(AgentRun).where(AgentRun.id == run_id).with_for_update())
            if run is None:
                raise LookupError(f"run {run_id!r} does not exist")
            if self._finish_cancelled(session, run):
                session.commit()
                return
            ensure_run_transition(RunStatus(run.status), RunStatus.FAILED)
            run.status = RunStatus.FAILED.value
            run.error_code = error_code
            run.error_message = redact_public_value(error_message)
            run.finished_at = _utcnow_naive()
            append_event(
                session,
                run_id=run.id,
                event_type="run.failed",
                payload_json={
                    "error_code": error_code,
                    "message": error_message,
                },
            )
            session.commit()

    def _finalize_cancelled(self, run_id: str) -> None:
        with self._session_factory() as session:
            run = session.scalar(select(AgentRun).where(AgentRun.id == run_id).with_for_update())
            if run is not None and self._finish_cancelled(session, run):
                session.commit()

    @staticmethod
    def _finish_cancelled(session: Session, run: AgentRun) -> bool:
        if run.status != RunStatus.CANCELLING.value or run.cancel_requested_at is None:
            return False
        ensure_run_transition(RunStatus.CANCELLING, RunStatus.CANCELLED)
        run.status = RunStatus.CANCELLED.value
        run.finished_at = _utcnow_naive()
        append_event(session, run_id=run.id, event_type="run.cancelled", payload_json={})
        return True


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
