/** 模块职责：定义后端任务资源在前端使用的稳定类型。 */

export interface Task {
  id: number;
  parent_id: number | null;
  owner_id: number;
  title: string;
  description: string | null;
  priority: "high" | "medium" | "low";
  status: "todo" | "in_progress" | "done";
  due_date: string | null;
  tag: string | null;
  task_type: "short_term" | "long_term" | "daily";
  deadline_precision: "day" | "month" | "year" | null;
  timer_preset: number | null;
  timer_total_seconds: number;
  created_at: string;
  updated_at: string;
}
