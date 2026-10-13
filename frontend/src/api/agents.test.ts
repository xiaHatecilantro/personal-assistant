import { beforeEach, expect, it, vi } from "vitest";
import client from "./client";
import { cancelRun, createRun, decideApproval, fetchRunEvents, fetchRuns, resumeRun } from "./agents";

vi.mock("./client", () => ({ default: { get: vi.fn(), post: vi.fn() } }));

beforeEach(() => vi.clearAllMocks());

it("Run 列表、创建与事件使用既有认证客户端和真实路径", async () => {
  await fetchRuns();
  await createRun("整理任务");
  await fetchRunEvents("run-1", 3);
  expect(client.get).toHaveBeenCalledWith("/agent/runs");
  expect(client.post).toHaveBeenCalledWith("/agent/runs", { goal: "整理任务" });
  expect(client.get).toHaveBeenCalledWith("/agent/runs/run-1/events", { params: { after: 3 } });
});

it("审批编辑携带 revision 与修改后的参数", async () => {
  await decideApproval("run-1", "approval-1", {
    decision: "edit",
    revision: 2,
    edited_arguments: { title: "修订任务" },
  });
  expect(client.post).toHaveBeenCalledWith("/agent/runs/run-1/approvals/approval-1/decision", {
    decision: "edit",
    revision: 2,
    edited_arguments: { title: "修订任务" },
  });
});

it("取消与重启恢复均走当前用户认证客户端", async () => {
  await cancelRun("run/1");
  await resumeRun("run/1");
  expect(client.post).toHaveBeenCalledWith("/agent/runs/run%2F1/cancel");
  expect(client.post).toHaveBeenCalledWith("/agent/runs/run%2F1/resume");
});
