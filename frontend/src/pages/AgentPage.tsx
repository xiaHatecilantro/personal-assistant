/** Agent 工作台：服务端快照承载恢复，SSE 只增量补充当前运行事件。 */

import { ClockCircleOutlined, ExclamationCircleOutlined, ReloadOutlined, RobotOutlined, StopOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, App, Button, Empty, Space, Spin, Tag, Typography } from "antd";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { cancelRun, createRun, decideApproval, fetchApprovals, fetchRun, fetchRunEvents, fetchRuns, resumeRun } from "../api/agents";
import { connectRunEvents, isRunTerminal, mergeEvents } from "../api/agentStream";
import ApprovalCard from "../components/agent/ApprovalCard";
import RunComposer from "../components/agent/RunComposer";
import RunSummary from "../components/agent/RunSummary";
import RunTimeline from "../components/agent/RunTimeline";
import { useAuthStore } from "../store/authStore";
import type { AgentEvent, ApprovalDecision } from "../types/agent";
import "./AgentPage.css";

const statusLabel: Record<string, string> = {
  queued: "排队中", running: "运行中", waiting_approval: "等待审批",
  completed: "已完成", failed: "失败", cancelling: "取消中",
  interrupted: "已中断", cancelled: "已取消",
};

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : "请求失败，请稍后重试";
}

export default function AgentPage() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const ownerId = useAuthStore((state) => state.user?.id);
  const { message } = App.useApp();
  const [streamError, setStreamError] = useState<{ ownerId: number; runId: string; message: string } | null>(null);
  // 401 退出不会自动清空 Query 缓存；将用户 ID 纳入 key，避免下一位用户看到上一位的快照。
  const runs = useQuery({ queryKey: ["agent", ownerId, "runs"], queryFn: fetchRuns, enabled: ownerId !== undefined });
  const run = useQuery({
    queryKey: ["agent", ownerId, "run", runId], queryFn: () => fetchRun(runId!), enabled: ownerId !== undefined && Boolean(runId),
    refetchInterval: (query) => query.state.data && !isRunTerminal(query.state.data.status) ? 5000 : false,
  });
  const events = useQuery({ queryKey: ["agent", ownerId, "events", runId], queryFn: () => fetchRunEvents(runId!), enabled: ownerId !== undefined && Boolean(runId) });
  const approvals = useQuery({
    queryKey: ["agent", ownerId, "approvals", runId], queryFn: () => fetchApprovals(runId!),
    enabled: ownerId !== undefined && Boolean(runId && run.data?.status === "waiting_approval"),
  });
  const create = useMutation({
    mutationFn: createRun,
    onSuccess: (created) => {
      if (useAuthStore.getState().user?.id !== ownerId) return;
      queryClient.invalidateQueries({ queryKey: ["agent", ownerId, "runs"] });
      navigate(`/agent/${created.id}`);
      message.success("运行已创建");
    },
    onError: (error) => message.error(errorText(error)),
  });
  const decision = useMutation({
    mutationFn: ({ approvalId, value }: { approvalId: string; value: ApprovalDecision }) => decideApproval(runId!, approvalId, value),
    onSuccess: () => {
      if (useAuthStore.getState().user?.id !== ownerId) return;
      queryClient.invalidateQueries({ queryKey: ["agent", ownerId, "approvals", runId] });
      queryClient.invalidateQueries({ queryKey: ["agent", ownerId, "run", runId] });
      message.success("审批决定已提交");
    },
    onError: (error) => message.error(errorText(error)),
  });
  const cancel = useMutation({
    mutationFn: () => cancelRun(runId!),
    onSuccess: (updated) => {
      if (useAuthStore.getState().user?.id !== ownerId) return;
      queryClient.setQueryData(["agent", ownerId, "run", runId], updated);
      queryClient.invalidateQueries({ queryKey: ["agent", ownerId, "runs"] });
      message.success("取消请求已提交");
    },
    onError: (error) => message.error(errorText(error)),
  });
  const resume = useMutation({
    mutationFn: () => resumeRun(runId!),
    onSuccess: (updated) => {
      if (useAuthStore.getState().user?.id !== ownerId) return;
      queryClient.setQueryData(["agent", ownerId, "run", runId], updated);
      queryClient.invalidateQueries({ queryKey: ["agent", ownerId, "runs"] });
      queryClient.invalidateQueries({ queryKey: ["agent", ownerId, "approvals", runId] });
      message.success("恢复请求已提交");
    },
    onError: (error) => message.error(errorText(error)),
  });

  // 首次获取历史事件后才连接；断线由连接器记住最后 sequence，刷新则从 REST 重新计算。
  useEffect(() => {
    if (ownerId === undefined || !runId || !run.isSuccess || !events.isSuccess || isRunTerminal(run.data.status)) return;
    const controller = new AbortController();
    const after = Math.max(0, ...(events.data ?? []).map((event) => event.sequence));
    void connectRunEvents({
      runId, after, signal: controller.signal,
      onEvent: (event) => {
        queryClient.setQueryData<AgentEvent[]>(["agent", ownerId, "events", runId], (current) => mergeEvents(current ?? [], [event]));
        if (event.type === "approval.required" || event.type === "approval.resolved") {
          queryClient.invalidateQueries({ queryKey: ["agent", ownerId, "approvals", runId] });
        }
        if (event.type.startsWith("run.") || event.type.startsWith("approval.")) {
          queryClient.invalidateQueries({ queryKey: ["agent", ownerId, "run", runId] });
          queryClient.invalidateQueries({ queryKey: ["agent", ownerId, "runs"] });
        }
        setStreamError(null);
      },
      onError: (error) => setStreamError({ ownerId, runId, message: error.message }),
    });
    return () => controller.abort();
    // data 变化来自同一条连接，不能为每个事件重新开启 SSE。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ownerId, runId, run.isSuccess, events.isSuccess, run.data?.status === "completed" || run.data?.status === "failed" || run.data?.status === "cancelled" || run.data?.status === "interrupted", queryClient]);

  const activeEvents = events.data ?? [];
  const pendingApprovals = approvals.data?.filter((item) => item.status === "pending") ?? [];
  const toolCount = activeEvents.filter((event) => event.type === "tool.completed" || event.type === "tool.failed").length;

  return <div className="agent-page">
    <div className="agent-page-heading">
      <div><Typography.Text className="agent-eyebrow">SEEKFLOW / AGENT WORKBENCH</Typography.Text><Typography.Title level={2} style={{ margin: "5px 0 2px" }}>Agent 工作台</Typography.Title><Typography.Text type="secondary">目标、执行轨迹和人工审批，集中在一次运行里。</Typography.Text></div>
      <div className="agent-heading-mark" aria-hidden="true"><RobotOutlined /></div>
    </div>
    <div className="agent-workspace">
      <aside className="agent-sidebar">
        <RunComposer onSubmit={(goal) => create.mutate(goal)} submitting={create.isPending} />
        <section className="agent-panel agent-run-list"><div className="agent-panel-heading"><Typography.Text strong>运行记录</Typography.Text><Button type="text" size="small" aria-label="刷新运行记录" icon={<ReloadOutlined />} onClick={() => runs.refetch()} /></div>
          {runs.isPending ? <Spin aria-label="加载运行记录" /> : runs.isError ? <Alert type="error" showIcon message="运行记录加载失败" action={<Button size="small" onClick={() => runs.refetch()}>重试</Button>} /> : !runs.data?.length ? <Empty description="还没有运行记录" image={Empty.PRESENTED_IMAGE_SIMPLE} /> : <div className="agent-runs">{runs.data.map((item) => <button key={item.id} className={`agent-run-item ${item.id === runId ? "is-active" : ""}`} onClick={() => navigate(`/agent/${item.id}`)}><span className="agent-run-item-goal">{item.goal}</span><span className="agent-run-item-meta"><ClockCircleOutlined /> {new Date(item.created_at).toLocaleString("zh-CN")} · {statusLabel[item.status] ?? item.status}</span></button>)}</div>}
        </section>
      </aside>
      <div className="agent-main">
        {!runId ? <section className="agent-panel agent-welcome"><RobotOutlined className="agent-welcome-icon" /><Typography.Title level={4}>选择运行，查看完整执行记录</Typography.Title><Typography.Text type="secondary">你也可以在左侧输入目标，开启一次新运行。</Typography.Text></section> : run.isPending ? <section className="agent-panel agent-loading"><Spin tip="正在读取运行快照" /></section> : run.isError || !run.data ? <Alert type="error" showIcon message="运行详情加载失败" description={errorText(run.error)} action={<Button onClick={() => run.refetch()}>重试</Button>} /> : <>
          <section className="agent-panel agent-run-header"><div><Typography.Text className="agent-eyebrow">RUN / {run.data.id.slice(0, 8)}</Typography.Text><Typography.Title level={3} style={{ margin: "7px 0" }}>{run.data.goal}</Typography.Title><Tag color={run.data.status === "completed" ? "success" : run.data.status === "failed" ? "error" : run.data.status === "waiting_approval" ? "warning" : "processing"}>{statusLabel[run.data.status] ?? run.data.status}</Tag></div>{run.data.status === "interrupted" ? <Space><Button icon={<ReloadOutlined />} loading={resume.isPending} onClick={() => resume.mutate()}>恢复运行</Button><Button icon={<StopOutlined />} loading={cancel.isPending} onClick={() => cancel.mutate()}>取消运行</Button></Space> : (run.data.status === "running" || run.data.status === "waiting_approval") ? <Button icon={<StopOutlined />} loading={cancel.isPending} onClick={() => cancel.mutate()}>取消运行</Button> : null}</section>
          {streamError && streamError.ownerId === ownerId && streamError.runId === runId && <Alert type="warning" showIcon icon={<ExclamationCircleOutlined />} message="实时连接中断，正在自动重连" description={streamError.message} />}
          {run.data.status === "interrupted" && <Alert type="warning" showIcon message="运行已中断" description="可沿原执行记录和 Checkpoint 恢复；恢复前不会自动执行。" />}
          {run.data.status === "waiting_approval" && <section className="agent-panel"><div className="agent-section-heading"><Typography.Text className="agent-eyebrow">ACTION REQUIRED</Typography.Text><Typography.Title level={4}>等待你的审批</Typography.Title></div>{approvals.isPending ? <Spin aria-label="加载审批" /> : approvals.isError ? <Alert type="error" showIcon message="审批信息加载失败" action={<Button onClick={() => approvals.refetch()}>重试</Button>} /> : pendingApprovals.length ? pendingApprovals.map((item) => <ApprovalCard key={item.id} approval={item} submitting={decision.isPending} onDecision={(value) => decision.mutate({ approvalId: item.id, value })} />) : <Empty description="暂无待处理审批" image={Empty.PRESENTED_IMAGE_SIMPLE} />}</section>}
          <section className="agent-panel"><div className="agent-section-heading"><Typography.Text className="agent-eyebrow">EXECUTION LOG</Typography.Text><Typography.Title level={4}>执行时间线</Typography.Title></div>{events.isPending ? <Spin aria-label="加载事件" /> : events.isError ? <Alert type="error" showIcon message="事件加载失败" action={<Button onClick={() => events.refetch()}>重试</Button>} /> : <RunTimeline events={activeEvents} />}</section>
          {run.data.status !== "interrupted" && isRunTerminal(run.data.status) && <RunSummary run={run.data} toolCount={toolCount} />}
        </>}
      </div>
    </div>
  </div>;
}
