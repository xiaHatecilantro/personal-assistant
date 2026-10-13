/** Bearer SSE：解析分块、按 sequence 去重，并从最后确认的序号重连。 */

import { runStreamUrl } from "./agents";
import { useAuthStore } from "../store/authStore";
import { terminalRunStatuses, type AgentEvent } from "../types/agent";

export function mergeEvents(existing: AgentEvent[], incoming: AgentEvent[]): AgentEvent[] {
  const bySequence = new Map(existing.map((event) => [event.sequence, event]));
  for (const event of incoming) bySequence.set(event.sequence, event);
  return [...bySequence.values()].sort((a, b) => a.sequence - b.sequence);
}

export function createSseParser() {
  let buffer = "";
  return {
    push(chunk: string): AgentEvent[] {
      buffer = (buffer + chunk).replaceAll("\r\n", "\n");
      const result: AgentEvent[] = [];
      let boundary = buffer.indexOf("\n\n");
      while (boundary >= 0) {
        const block = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const fields = block.split("\n");
        const eventType = fields.find((line) => line.startsWith("event:"))?.slice(6).trim();
        const id = Number(fields.find((line) => line.startsWith("id:"))?.slice(3).trim());
        const data = fields.filter((line) => line.startsWith("data:")).map((line) => line.slice(5).trimStart()).join("\n");
        if (eventType !== "heartbeat" && Number.isSafeInteger(id) && id > 0 && data) {
          try {
            const parsed: unknown = JSON.parse(data);
            if (isAgentEvent(parsed) && parsed.sequence === id) result.push(parsed);
          } catch {
            // 单条畸形事件不应破坏后续事件的断线恢复。
          }
        }
        boundary = buffer.indexOf("\n\n");
      }
      return result;
    },
  };
}

function isAgentEvent(value: unknown): value is AgentEvent {
  if (typeof value !== "object" || value === null) return false;
  const event = value as Partial<AgentEvent>;
  return event.schema_version === 1 && typeof event.run_id === "string"
    && typeof event.sequence === "number" && typeof event.type === "string"
    && typeof event.created_at === "string" && typeof event.data === "object" && event.data !== null;
}

function delay(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    if (signal.aborted) return resolve();
    const timer = window.setTimeout(done, ms);
    signal.addEventListener("abort", done, { once: true });
    function done() {
      window.clearTimeout(timer);
      signal.removeEventListener("abort", done);
      resolve();
    }
  });
}

export async function connectRunEvents(options: {
  runId: string;
  after: number;
  signal: AbortSignal;
  onEvent: (event: AgentEvent) => void;
  onError: (error: Error) => void;
}): Promise<void> {
  let after = options.after;
  while (!options.signal.aborted) {
    try {
      const token = useAuthStore.getState().token;
      const response = await fetch(`/api/v1${runStreamUrl(options.runId, after)}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        signal: options.signal,
      });
      if (response.status === 401) useAuthStore.getState().logout();
      if (!response.ok || !response.body) throw new Error(`事件连接失败（HTTP ${response.status}）`);
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      const parser = createSseParser();
      let completed = false;
      while (!options.signal.aborted) {
        const { done, value } = await reader.read();
        if (done) break;
        for (const event of parser.push(decoder.decode(value, { stream: true }))) {
          if (event.run_id !== options.runId || event.sequence <= after) continue;
          after = event.sequence;
          options.onEvent(event);
          if (event.type === "run.completed" || event.type === "run.failed" || event.type === "run.cancelled" || event.type === "run.interrupted") completed = true;
        }
        if (completed) return;
      }
    } catch (error) {
      if (options.signal.aborted) return;
      options.onError(error instanceof Error ? error : new Error("事件连接失败"));
      if (error instanceof Error && /HTTP 4\d\d/.test(error.message)) return;
    }
    if (!options.signal.aborted) await delay(1000, options.signal);
  }
}

export function isRunTerminal(status: string): boolean {
  return terminalRunStatuses.has(status);
}
