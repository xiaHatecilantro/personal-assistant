import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import ApprovalCard from "./ApprovalCard";
import type { ApprovalSummary } from "../../types/agent";

const approval: ApprovalSummary = {
  id: "approval-1", run_id: "run-1", tool_call_id: "call-1",
  tool_name: "create_task", arguments: { title: "原任务" },
  status: "pending", revision: 1, decision: null,
  created_at: "2026-10-09T00:00:00Z", reviewed_at: null,
};

it("审批前二次确认且提交期间无法重复点击", () => {
  const onDecision = vi.fn();
  render(<ApprovalCard approval={approval} submitting={false} onDecision={onDecision} />);
  fireEvent.click(screen.getByRole("button", { name: "批准" }));
  expect(onDecision).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "确认批准" }));
  expect(onDecision).toHaveBeenCalledWith({ decision: "approve", revision: 1 });
});

it("仅 pending 审批可操作", () => {
  render(<ApprovalCard approval={{ ...approval, status: "approved" }} submitting={false} onDecision={vi.fn()} />);
  expect(screen.queryByRole("button", { name: "批准" })).not.toBeInTheDocument();
});

it("编辑参数必须是 JSON 对象，并在二次确认后提交", () => {
  const onDecision = vi.fn();
  render(<ApprovalCard approval={approval} submitting={false} onDecision={onDecision} />);
  fireEvent.click(screen.getByRole("button", { name: "编辑后批准" }));
  fireEvent.change(screen.getByRole("textbox", { name: "编辑工具参数" }), { target: { value: '{"title":"新任务"}' } });
  fireEvent.click(screen.getByRole("button", { name: "确认提交编辑" }));
  expect(onDecision).toHaveBeenCalledWith({ decision: "edit", revision: 1, edited_arguments: { title: "新任务" } });
});
