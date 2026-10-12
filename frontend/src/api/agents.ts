/** Agent REST 契约集中在此，页面只处理展示与交互。 */

import client from "./client";
import type { AgentEvent, ApprovalDecision, ApprovalSummary, RunDetail, RunSummary } from "../types/agent";

const base = "/agent/runs";

export function fetchRuns(): Promise<RunSummary[]> {
  return client.get(base);
}

export function createRun(goal: string): Promise<RunDetail> {
  return client.post(base, { goal });
}

export function fetchRun(runId: string): Promise<RunDetail> {
  return client.get(`${base}/${encodeURIComponent(runId)}`);
}

export function cancelRun(runId: string): Promise<RunDetail> {
  return client.post(`${base}/${encodeURIComponent(runId)}/cancel`);
}

export function resumeRun(runId: string): Promise<RunDetail> {
  return client.post(`${base}/${encodeURIComponent(runId)}/resume`);
}

export function fetchRunEvents(runId: string, after = 0): Promise<AgentEvent[]> {
  return client.get(`${base}/${encodeURIComponent(runId)}/events`, { params: { after } });
}

export function fetchApprovals(runId: string): Promise<ApprovalSummary[]> {
  return client.get(`${base}/${encodeURIComponent(runId)}/approvals`);
}

export function decideApproval(runId: string, approvalId: string, decision: ApprovalDecision): Promise<ApprovalSummary> {
  return client.post(
    `${base}/${encodeURIComponent(runId)}/approvals/${encodeURIComponent(approvalId)}/decision`,
    decision,
  );
}

// SSE 采用 fetch ReadableStream 才能携带现有 Bearer Token；URL 在一处维护以跟随后端路由。
export function runStreamUrl(runId: string, after: number): string {
  return `${base}/${encodeURIComponent(runId)}/events/stream?after=${after}`;
}
