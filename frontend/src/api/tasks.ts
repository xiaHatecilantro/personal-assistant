import client from "./client";
import type { Task } from "../types/task";

export function fetchTasks(params?: {
  task_type?: string;
  status?: string;
  priority?: string;
  tag?: string;
  parent_id?: number | null;
}): Promise<Task[]> {
  return client.get("/tasks", { params });
}

export function fetchTask(id: number): Promise<Task> {
  return client.get(`/tasks/${id}`);
}

export function createTask(data: TaskCreate): Promise<Task> {
  return client.post("/tasks", data);
}

export function updateTask(id: number, data: TaskUpdate): Promise<Task> {
  return client.put(`/tasks/${id}`, data);
}

export function deleteTask(id: number): Promise<void> {
  return client.delete(`/tasks/${id}`);
}

export function updateTimer(
  id: number,
  total_seconds: number,
): Promise<{ timer_total_seconds: number }> {
  return client.patch(`/tasks/${id}/timer`, { total_seconds });
}

export interface TaskCreate {
  title: string;
  description?: string | null;
  priority?: string;
  status?: string;
  due_date?: string | null;
  tag?: string | null;
  task_type?: string;
  deadline_precision?: string | null;
  timer_preset?: number | null;
  parent_id?: number | null;
}

export interface TaskUpdate {
  title: string;
  description?: string | null;
  priority: string;
  status: string;
  due_date?: string | null;
  tag?: string | null;
  task_type: string;
  deadline_precision?: string | null;
  timer_preset?: number | null;
}
