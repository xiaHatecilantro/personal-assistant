import { describe, expect, it, vi } from "vitest";
import { connectRunEvents, createSseParser, isRunTerminal, mergeEvents } from "./agentStream";
import type { AgentEvent } from "../types/agent";

const event = {
  schema_version: 1,
  run_id: "run-1",
  sequence: 2,
  type: "plan.updated",
  created_at: "2026-10-09T00:00:00Z",
  data: { steps: ["检查任务"] },
} satisfies AgentEvent;

describe("Agent SSE", () => {
  it("任意分块都还原事件 ID，忽略 heartbeat 和残缺尾部", () => {
    const input = `id: 2\nevent: plan.updated\ndata: ${JSON.stringify(event)}\n\nevent: heartbeat\ndata: {}\n\nid: 3\ndata: {`;
    for (let size = 1; size <= input.length; size += 1) {
      const parser = createSseParser();
      const received = [];
      for (let offset = 0; offset < input.length; offset += size) {
        received.push(...parser.push(input.slice(offset, offset + size)));
      }
      expect(received).toEqual([event]);
    }
  });

  it("按 sequence 去重排序，重连回放不重复卡片", () => {
    const first = { ...event, sequence: 1 };
    expect(mergeEvents([event], [first, event])).toEqual([first, event]);
  });

  it("连接关闭后从最后序号重连，并过滤服务端重复回放", async () => {
    const completed = { ...event, sequence: 3, type: "run.completed" };
    const response = (events: AgentEvent[]) => ({
      ok: true, status: 200,
      body: { getReader: () => {
        let delivered = false;
        return { read: async () => {
          if (delivered) return { done: true, value: undefined };
          delivered = true;
          return { done: false, value: new TextEncoder().encode(events.map((item) => `id: ${item.sequence}\nevent: ${item.type}\ndata: ${JSON.stringify(item)}\n\n`).join("")) };
        } };
      } },
    }) as Response;
    const mockFetch = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(response([event]))
      .mockResolvedValueOnce(response([event, completed]));
    const received: AgentEvent[] = [];
    try {
      await connectRunEvents({ runId: "run-1", after: 0, signal: new AbortController().signal,
        onEvent: (item) => received.push(item), onError: vi.fn() });
      expect(received).toEqual([event, completed]);
      expect(mockFetch.mock.calls[0][0]).toContain("after=0");
      expect(mockFetch.mock.calls[1][0]).toContain("after=2");
    } finally {
      mockFetch.mockRestore();
    }
  });

  it("已中断 Run 是当前工作台观察终点", () => {
    expect(isRunTerminal("interrupted")).toBe(true);
  });

  it("收到 run.interrupted 后关闭连接且不再重连", async () => {
    const interrupted = { ...event, type: "run.interrupted" };
    let readCount = 0;
    const mockFetch = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true, status: 200,
      body: { getReader: () => ({ read: async () => {
        readCount += 1;
        return { done: false, value: new TextEncoder().encode(`id: 2\nevent: run.interrupted\ndata: ${JSON.stringify(interrupted)}\n\n`) };
      } }) },
    } as Response);
    try {
      await connectRunEvents({ runId: "run-1", after: 0, signal: new AbortController().signal,
        onEvent: vi.fn(), onError: vi.fn() });
      expect(readCount).toBe(1);
      expect(mockFetch).toHaveBeenCalledTimes(1);
    } finally {
      mockFetch.mockRestore();
    }
  });
});
