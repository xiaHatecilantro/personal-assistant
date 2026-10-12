import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import RunTimeline from "./RunTimeline";
import type { AgentEvent } from "../../types/agent";

const base: AgentEvent = {
  schema_version: 1, run_id: "run-1", sequence: 1,
  type: "plan.updated", created_at: "2026-10-09T00:00:00Z", data: { items: ["检索笔记"] },
};

it("乱序事件按 sequence 展示，未知事件安全降级", () => {
  render(<RunTimeline events={[{ ...base, sequence: 3, type: "future.event", data: { text: "新协议" } }, base]} />);
  expect(screen.getByText("检索笔记").compareDocumentPosition(screen.getByText("其他事件")) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(screen.getByText("future.event")).toBeInTheDocument();
});
