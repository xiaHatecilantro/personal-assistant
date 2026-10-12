import { App as AntApp } from "antd";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { expect, it, vi } from "vitest";
import AgentPage from "./AgentPage";
import { cancelRun, fetchRun, fetchRunEvents, fetchRuns, resumeRun } from "../api/agents";
import { connectRunEvents } from "../api/agentStream";
import { useAuthStore } from "../store/authStore";
import type { RunDetail } from "../types/agent";

const { savedRun } = vi.hoisted(() => ({ savedRun: {
  id: "run-1", thread_id: "run-1", goal: "整理任务", status: "completed",
  graph_version: "read-v1", max_steps: 8, timeout_seconds: 120, step_count: 2,
  final_answer: "已整理三项任务", error_code: null, error_message: null,
  created_at: "2026-10-09T00:00:00Z", updated_at: "2026-10-09T00:00:08Z",
  started_at: "2026-10-09T00:00:01Z", finished_at: "2026-10-09T00:00:08Z",
} as RunDetail }));

vi.mock("../api/agents", () => ({
  fetchRuns: vi.fn(async () => [savedRun]),
  fetchRun: vi.fn(async () => savedRun),
  fetchRunEvents: vi.fn(async () => []),
  fetchApprovals: vi.fn(async () => []),
  createRun: vi.fn(), decideApproval: vi.fn(), cancelRun: vi.fn(), resumeRun: vi.fn(),
}));
vi.mock("../api/agentStream", () => ({
  connectRunEvents: vi.fn(), mergeEvents: vi.fn(),
  isRunTerminal: (status: string) => ["completed", "failed", "cancelled", "interrupted"].includes(status),
}));

it("刷新 /agent/:runId 后从服务端快照恢复终态结果", async () => {
  useAuthStore.getState().setAuth("token-a", { id: 1, username: "A" });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={queryClient}><AntApp><MemoryRouter initialEntries={["/agent/run-1"]}><Routes><Route path="/agent/:runId" element={<AgentPage />} /></Routes></MemoryRouter></AntApp></QueryClientProvider>);
  expect(await screen.findByText("已整理三项任务")).toBeInTheDocument();
  expect(screen.getByText("已完成")).toBeInTheDocument();
});

it("切换用户时不展示上一用户缓存的 Agent Run", async () => {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 60_000 } } });
  vi.mocked(fetchRuns).mockImplementation(async () => [{
    id: `run-${useAuthStore.getState().user?.id}`,
    goal: useAuthStore.getState().user?.id === 1 ? "A 的私有目标" : "B 的私有目标",
    status: "completed", created_at: savedRun.created_at, updated_at: savedRun.updated_at,
  }]);
  useAuthStore.getState().setAuth("token-a", { id: 1, username: "A" });
  render(<QueryClientProvider client={queryClient}><AntApp><MemoryRouter initialEntries={["/agent"]}><Routes><Route path="/agent" element={<AgentPage />} /></Routes></MemoryRouter></AntApp></QueryClientProvider>);
  expect(await screen.findByText("A 的私有目标")).toBeInTheDocument();
  act(() => useAuthStore.getState().setAuth("token-b", { id: 2, username: "B" }));
  expect(await screen.findByText("B 的私有目标")).toBeInTheDocument();
  expect(screen.queryByText("A 的私有目标")).not.toBeInTheDocument();
});

it("已中断快照不会开启 SSE 观察", async () => {
  useAuthStore.getState().setAuth("token-a", { id: 1, username: "A" });
  vi.mocked(connectRunEvents).mockClear();
  vi.mocked(fetchRunEvents).mockClear();
  let resolveRun!: (run: RunDetail) => void;
  vi.mocked(fetchRun).mockImplementationOnce(() => new Promise((resolve) => { resolveRun = resolve; }));
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={queryClient}><AntApp><MemoryRouter initialEntries={["/agent/run-1"]}><Routes><Route path="/agent/:runId" element={<AgentPage />} /></Routes></MemoryRouter></AntApp></QueryClientProvider>);
  await waitFor(() => expect(fetchRunEvents).toHaveBeenCalled());
  await act(async () => { await Promise.resolve(); });
  expect(connectRunEvents).not.toHaveBeenCalled();
  act(() => resolveRun({ ...savedRun, status: "interrupted", final_answer: null }));
  expect(await screen.findByText("运行已中断")).toBeInTheDocument();
  expect(connectRunEvents).not.toHaveBeenCalled();
});

it("查看 Run 详情时切换用户不显示前一用户的结果", async () => {
  useAuthStore.getState().setAuth("token-a", { id: 1, username: "A" });
  vi.mocked(fetchRun).mockImplementation(async () => {
    if (useAuthStore.getState().user?.id === 2) throw new Error("Run 不存在");
    return { ...savedRun, final_answer: "A 的私有答案" };
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 60_000 } } });
  render(<QueryClientProvider client={queryClient}><AntApp><MemoryRouter initialEntries={["/agent/run-1"]}><Routes><Route path="/agent/:runId" element={<AgentPage />} /></Routes></MemoryRouter></AntApp></QueryClientProvider>);
  expect(await screen.findByText("A 的私有答案")).toBeInTheDocument();
  act(() => useAuthStore.getState().setAuth("token-b", { id: 2, username: "B" }));
  expect(await screen.findByText("运行详情加载失败")).toBeInTheDocument();
  expect(screen.queryByText("A 的私有答案")).not.toBeInTheDocument();
});

it("运行中可取消，中断后可显式恢复", async () => {
  useAuthStore.getState().setAuth("token-a", { id: 1, username: "A" });
  vi.mocked(cancelRun).mockReset();
  vi.mocked(resumeRun).mockReset();
  vi.mocked(fetchRun).mockReset();
  vi.mocked(cancelRun).mockResolvedValue({ ...savedRun, status: "cancelled" });
  vi.mocked(resumeRun).mockResolvedValue({ ...savedRun, status: "running" });
  vi.mocked(fetchRun).mockResolvedValue({ ...savedRun, status: "running" });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={queryClient}><AntApp><MemoryRouter initialEntries={["/agent/run-1"]}><Routes><Route path="/agent/:runId" element={<AgentPage />} /></Routes></MemoryRouter></AntApp></QueryClientProvider>);
  fireEvent.click(await screen.findByRole("button", { name: /取消运行/ }));
  await waitFor(() => expect(cancelRun).toHaveBeenCalledWith("run-1"));
  queryClient.setQueryData(["agent", 1, "run", "run-1"], { ...savedRun, status: "interrupted" });
  expect(await screen.findByRole("button", { name: /取消运行/ })).toBeInTheDocument();
  fireEvent.click(await screen.findByRole("button", { name: /恢复运行/ }));
  await waitFor(() => expect(resumeRun).toHaveBeenCalledWith("run-1"));
});
