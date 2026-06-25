import { DeleteOutlined, EditOutlined, PlusOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { App, Button, Popconfirm, Segmented, Spin } from "antd";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "motion/react";
import { deleteTask, fetchTasks } from "../api/tasks";
import TaskFilterBar from "../components/TaskFilterBar";
import { useFilterStore } from "../store/filterStore";
import type { Task } from "../types/task";

const statusMap: Record<string, { color: string; text: string }> = {
  todo: { color: "#d9d9d9", text: "待办" },
  in_progress: { color: "#1677ff", text: "进行中" },
  done: { color: "#52c41a", text: "已完成" },
};

const priorityColors: Record<string, string> = { high: "#f5222d", medium: "#fa8c16", low: "#52c41a" };
const priorityLabels: Record<string, string> = { high: "高", medium: "中", low: "低" };
const typeLabels: Record<string, string> = { short_term: "短期", long_term: "长期", daily: "每日" };

function TaskCard({ task, delay }: { task: Task; delay: number }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { message } = App.useApp();
  const isDone = task.status === "done";
  const st = statusMap[task.status] || statusMap.todo;

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteTask(id),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["tasks"] }); message.success("已删除"); },
  });

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay, ease: [0.25, 1, 0.5, 1] }}
      onClick={() => navigate(`/tasks/${task.id}`)}
      style={{
        background: "#fff",
        borderRadius: 16,
        border: "1px solid #f0f0f0",
        padding: "18px 22px",
        cursor: "pointer",
        transition: "box-shadow 0.15s",
        display: "flex",
        alignItems: "center",
        gap: 16,
      }}
      onMouseEnter={(e) => { (e.currentTarget as HTMLDivElement).style.boxShadow = "0 4px 20px rgba(0,0,0,0.06)"; }}
      onMouseLeave={(e) => { (e.currentTarget as HTMLDivElement).style.boxShadow = "none"; }}
    >
      {/* 左侧色条 */}
      <div style={{
        width: 4, height: 44, borderRadius: 2,
        background: priorityColors[task.priority] || "#d9d9d9",
        flexShrink: 0,
      }} />
      {/* 标题 */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontSize: 15, fontWeight: 500,
          color: isDone ? "#bbb" : "#333",
          textDecoration: isDone ? "line-through" : "none",
          marginBottom: 4,
          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
        }}>
          {task.title}
        </div>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
          <span style={{
            fontSize: 11, padding: "1px 8px", borderRadius: 6,
            background: st.color, color: "#fff", fontWeight: 500,
          }}>
            {st.text}
          </span>
          <span style={{
            fontSize: 11, padding: "1px 8px", borderRadius: 6,
            background: "#f5f5f5", color: "#999",
          }}>
            {typeLabels[task.task_type] || task.task_type}
          </span>
          <span style={{ fontSize: 12, fontWeight: 500, color: priorityColors[task.priority] || "#999" }}>
            {priorityLabels[task.priority]}优先
          </span>
          {task.tag && (
            <span style={{ fontSize: 11, color: "#bbb" }}>{task.tag}</span>
          )}
          {task.due_date && (
            <span style={{ fontSize: 11, color: "#bbb" }}>截止 {task.due_date}</span>
          )}
        </div>
      </div>
      {/* 操作 */}
      <div style={{ display: "flex", gap: 4, flexShrink: 0 }} onClick={(e) => e.stopPropagation()}>
        <Button type="text" size="small" icon={<EditOutlined />}
          onClick={(e) => { e.stopPropagation(); navigate(`/tasks/${task.id}`); }} />
        <Popconfirm
          title="确定删除？" okText="删除" cancelText="取消" okButtonProps={{ danger: true }}
          onConfirm={(e) => { e?.stopPropagation(); deleteMutation.mutate(task.id); }}
          onCancel={(e) => e?.stopPropagation()}
        >
          <Button type="text" danger size="small" icon={<DeleteOutlined />} />
        </Popconfirm>
      </div>
    </motion.div>
  );
}

export default function TaskListPage() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState("short_term");
  const { status, priority, tag } = useFilterStore();

  const { data: allTasks, isLoading } = useQuery({
    queryKey: ["tasks", { task_type: activeTab, status, priority, tag }],
    queryFn: () => fetchTasks({ task_type: activeTab, status: status || undefined, priority: priority || undefined, tag: tag || undefined }),
  });

  const tasks = allTasks || [];

  return (
    <div style={{ maxWidth: 800, margin: "0 auto", paddingTop: 8, height: "100%", overflow: "auto" }}>
      {/* 顶部 */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <Segmented
          value={activeTab}
          onChange={(v) => setActiveTab(v as string)}
          options={[
            { value: "short_term", label: "短期" },
            { value: "long_term", label: "长期" },
            { value: "daily", label: "每日" },
          ]}
        />
        <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate("/tasks/new")} style={{ borderRadius: 10 }}>
          新建任务
        </Button>
      </div>

      <TaskFilterBar />

      <Spin spinning={isLoading}>
        {tasks.length === 0 ? (
          <div style={{ textAlign: "center", padding: 60, background: "#fff", borderRadius: 20, border: "1px solid #f0f0f0" }}>
            <div style={{ fontSize: 40, opacity: 0.3, marginBottom: 12 }}>📋</div>
            <div style={{ fontSize: 15, color: "#999" }}>
              {activeTab === "daily" ? "还没有每日任务" : activeTab === "long_term" ? "还没有长期任务" : "还没有短期任务"}
            </div>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {tasks.map((t, i) => (
              <TaskCard key={t.id} task={t} delay={i * 0.03} />
            ))}
          </div>
        )}
      </Spin>
    </div>
  );
}
