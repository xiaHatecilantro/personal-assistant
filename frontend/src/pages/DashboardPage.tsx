import { useQuery } from "@tanstack/react-query";
import { Skeleton } from "antd";
import {
  CheckCircleOutlined,
  FireOutlined,
  ClockCircleOutlined,
  ArrowRightOutlined,
} from "@ant-design/icons";
import {
  Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { motion } from "motion/react";
import { useNavigate } from "react-router-dom";
import client from "../api/client";
import TaskBoard from "../components/ui/agent-plan";
import { fetchTasks } from "../api/tasks";
import type { Task as TaskType } from "../types/task";
import { useContext } from "react";
import { ThemeModeContext } from "../themeModeContext";
import EmptyState from "../components/ui/EmptyState";

interface Overview {
  total: number;
  by_status: Record<string, number>;
  by_priority: Record<string, number>;
}

interface Trend {
  daily_completed: { date: string; count: number }[];
}

/* ── 统计卡片 ── */

const statCards = [
  { key: "in_progress", label: "进行中", icon: <FireOutlined />, color: "#1677ff", bg: "#e6f4ff", darkBg: "#0d2137" },
  { key: "todo", label: "待办", icon: <ClockCircleOutlined />, color: "#fa8c16", bg: "#fff7e6", darkBg: "#2e2410" },
  { key: "done", label: "已完成", icon: <CheckCircleOutlined />, color: "#52c41a", bg: "#f0fdf4", darkBg: "#0d2818" },
];

function StatCard({ label, value, icon, color, bg, darkBg, delay }: {
  label: string; value?: number; icon: React.ReactNode;
  color: string; bg: string; darkBg: string; delay: number;
}) {
  const { themeMode } = useContext(ThemeModeContext);
  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, delay, ease: [0.25, 1, 0.5, 1] }}
      style={{
        background: themeMode === "dark" ? darkBg : bg,
        borderRadius: 20,
        padding: "28px 32px",
        display: "flex",
        alignItems: "center",
        gap: 22,
        flex: 1,
        minWidth: 200,
        position: "relative",
        overflow: "hidden",
      }}
    >
      <div style={{
        position: "absolute", right: -30, top: -30, width: 120, height: 120,
        borderRadius: "50%", background: color, opacity: 0.07,
      }} />
      <div style={{
        width: 56, height: 56, borderRadius: 16, background: color,
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: 26, color: "#fff", flexShrink: 0,
      }}>
        {icon}
      </div>
      <div style={{ position: "relative", zIndex: 1 }}>
        <div style={{ fontSize: 40, fontWeight: 800, color, lineHeight: 1 }}>
          {value !== undefined ? value : <Skeleton.Input active size="small" style={{ width: 40, height: 32 }} />}
        </div>
        <div style={{ fontSize: 14, color: "#8c8c8c", marginTop: 4, fontWeight: 500 }}>{label}</div>
      </div>
    </motion.div>
  );
}

/* ── 任务行 ── */

function TaskRow({ task, delay }: { task: TaskType; delay: number }) {
  const navigate = useNavigate();
  const isDone = task.status === "done";
  const pColors: Record<string, string> = { high: "#f5222d", medium: "#fa8c16", low: "#52c41a" };

  return (
    <motion.div
      initial={{ opacity: 0, x: -16 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.3, delay, ease: [0.25, 1, 0.5, 1] }}
      onClick={() => navigate(`/tasks/${task.id}`)}
      style={{
        display: "flex", alignItems: "center", gap: 14,
        padding: "16px 20px", background: "#fff", borderRadius: 14,
        cursor: "pointer", border: "1px solid #f0f0f0",
        transition: "box-shadow 0.15s",
      }}
      onMouseEnter={(e) => { (e.currentTarget as HTMLDivElement).style.boxShadow = "0 2px 12px rgba(0,0,0,0.06)"; }}
      onMouseLeave={(e) => { (e.currentTarget as HTMLDivElement).style.boxShadow = "none"; }}
    >
      <div style={{ width: 4, height: 40, borderRadius: 2, background: pColors[task.priority] || "#d9d9d9", flexShrink: 0 }} />
      <span style={{
        flex: 1, fontSize: 15, fontWeight: isDone ? 400 : 500,
        color: isDone ? "#bbb" : "#333", textDecoration: isDone ? "line-through" : "none",
      }}>{task.title}</span>
      <span style={{ fontSize: 12, color: "#999", background: "#f5f5f5", padding: "3px 10px", borderRadius: 8, flexShrink: 0 }}>
        {task.task_type === "daily" ? "每日" : task.task_type === "long_term" ? "长期" : "短期"}
      </span>
      <ArrowRightOutlined style={{ color: "#ccc", fontSize: 12 }} />
    </motion.div>
  );
}

/* ═══════════════════════════════════════════ */

export default function DashboardPage() {
  const navigate = useNavigate();

  const { data: overview } = useQuery({
    queryKey: ["tasks", "stats", "overview"],
    queryFn: () => client.get("/tasks/stats/overview") as Promise<Overview>,
  });

  const { data: trend } = useQuery({
    queryKey: ["tasks", "stats", "trend"],
    queryFn: () => client.get("/tasks/stats/trend") as Promise<Trend>,
  });

  const { data: allTasks } = useQuery({
    queryKey: ["tasks"],
    queryFn: () => fetchTasks(),
    refetchInterval: 30_000,
  });

  const trendData = trend?.daily_completed.map((d) => ({ date: d.date.slice(5), count: d.count })) ?? [];
  const hasTrend = trendData.length > 0 && trendData.some((d) => d.count > 0);

  const todayTasks = (allTasks || [])
    .filter((t) => t.status !== "done")
    .sort((a, b) => ({ high: 0, medium: 1, low: 2 }[a.priority ?? "medium"] ?? 1) - ({ high: 0, medium: 1, low: 2 }[b.priority ?? "medium"] ?? 1))
    .slice(0, 5);

  return (
    <div style={{ maxWidth: 960, margin: "0 auto", padding: "16px 0 0", height: "100%", overflow: "auto" }}>

      {/* ── 三张统计卡 ── */}
      <div style={{ display: "flex", gap: 24 }}>
        {statCards.map((s, i) => (
          <StatCard key={s.key} label={s.label} icon={s.icon} color={s.color} bg={s.bg} darkBg={s.darkBg} value={overview?.by_status?.[s.key as keyof typeof overview.by_status] as number | undefined} delay={i * 0.08} />
        ))}
      </div>

      {/* ── 今日待办 + 趋势图 两栏 ── */}
      <div style={{ display: "flex", gap: 24, marginTop: 32 }}>
        {/* 左栏：今日待办 */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.25, ease: [0.25, 1, 0.5, 1] }}
          style={{ flex: 1, minWidth: 0 }}
        >
          <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 16 }}>
            <h3 style={{ fontSize: 18, fontWeight: 700, color: "#1a1a1a", margin: 0 }}>今日待办</h3>
            <span style={{ fontSize: 13, color: "#1677ff", cursor: "pointer", fontWeight: 500 }} onClick={() => navigate("/tasks")}>查看全部 →</span>
          </div>

          {todayTasks.length === 0 ? (
            <EmptyState icon="🎯" title="今天没有待办任务" hint="点击右下角 + 按钮创建一个吧" />
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {todayTasks.map((t, i) => <TaskRow key={t.id} task={t} delay={0.3 + i * 0.04} />)}
            </div>
          )}
        </motion.div>

        {/* 右栏：完成趋势 */}
        {hasTrend && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.3, ease: [0.25, 1, 0.5, 1] }}
            style={{
              flex: 1, minWidth: 0,
              background: "#fff", borderRadius: 20, border: "1px solid #f0f0f0", padding: "24px 28px",
            }}
          >
            <h3 style={{ fontSize: 18, fontWeight: 700, color: "#1a1a1a", margin: "0 0 12px" }}>完成趋势</h3>
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={trendData}>
                <XAxis dataKey="date" tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} axisLine={false} tickLine={false} width={28} />
                <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid #f0f0f0", boxShadow: "0 4px 16px rgba(0,0,0,0.06)", fontSize: 13 }} />
                <Line type="monotone" dataKey="count" name="完成" stroke="#1677ff" strokeWidth={2.5} dot={{ r: 0 }} activeDot={{ r: 5, fill: "#1677ff", stroke: "#fff", strokeWidth: 2 }} />
              </LineChart>
            </ResponsiveContainer>
          </motion.div>
        )}
      </div>

      {/* ── 全部任务 ── */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.4, ease: [0.25, 1, 0.5, 1] }}
        style={{ marginTop: 32, background: "#fff", borderRadius: 20, border: "1px solid #f0f0f0", overflow: "hidden" }}
      >
        <h3 style={{ fontSize: 18, fontWeight: 700, color: "#1a1a1a", margin: 0, padding: "24px 28px 12px" }}>全部任务</h3>
        <TaskBoard tasks={allTasks || []} />
      </motion.div>

    </div>
  );
}
