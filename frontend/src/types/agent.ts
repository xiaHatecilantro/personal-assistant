/** 与后端 Agent REST/SSE 契约对齐；未知事件仍由页面安全展示。 */

export type RunStatus =
  | "queued" | "running" | "waiting_approval" | "completed"
  | "failed" | "cancelling" | "interrupted" | "cancelled";

export interface RunSummary {
  id: string;
  goal: string;
  status: RunStatus;
  created_at: string;
  updated_at: string;
}

export interface RunDetail extends RunSummary {
  thread_id: string;
  graph_version: string;
  max_steps: number;
  timeout_seconds: number;
  step_count: number;
  final_answer: string | null;
  error_code: string | null;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface AgentEvent {
  schema_version: 1;
  run_id: string;
  sequence: number;
  type: string;
  created_at: string;
  data: Record<string, unknown>;
}

export interface ApprovalSummary {
  id: string;
  run_id: string;
  tool_call_id: string;
  tool_name: string;
  arguments: Record<string, unknown>;
  status: "pending" | "approved" | "rejected";
  revision: number;
  decision: "approve" | "reject" | "edit" | null;
  created_at: string;
  reviewed_at: string | null;
}

export type ApprovalDecision =
  | { decision: "approve" | "reject"; revision: number }
  | { decision: "edit"; revision: number; edited_arguments: Record<string, unknown> };

// M7 暂无 resume；interrupted 对页面观察是终点，M8 再通过显式恢复开启新观察。
export const terminalRunStatuses = new Set<string>(["completed", "failed", "cancelled", "interrupted"]);
