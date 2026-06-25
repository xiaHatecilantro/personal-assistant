import { useQuery } from "@tanstack/react-query";
import { Skeleton } from "antd";
import {
  CheckCircleOutlined,
  FireOutlined,
  ClockCircleOutlined,
  ArrowRightOutlined,
} from "@ant-design/icons";
import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { motion } from "motion/react";
import { useNavigate } from "react-router-dom";
import client from "../api/client";
import TaskBoard from "../components/ui/agent-plan";
import { fetchTasks } from "../api/tasks";
import type { Task as TaskType } from "../types/task";

interface Overview {
  total: number;
  by_status: Record<string, number>;
  by_priority: Record<string, number>;
}

interface Trend {
  daily_completed: { date: string; count: number }[];
}

/* ── 渐变统计卡片 ── */

const statCards = [
  {
    key: "in_progress",
    label: "进行中",
    icon: <FireOutlined />,
    gradient: "linear-gradient(135deg, #e6f4ff 0%, #d6e8ff 100%)",
    darkGradient: "linear-gradient(135deg, #0d2137 0%, #142842 100%)",
    color: "#1677ff",
  },
  {
    key: "todo",
    label: "待办",
    icon: <ClockCircleOutlined />,
    gradient: "linear-gradient(135deg, #fff7e6 0%, #ffe7ba 100%)",
    darkGradient: "linear-gradient(135deg, #2e2410 0%, #3d2e14 100%)",
    color: "#fa8c16",
  },
  {
    key: "done",
    label: "已完成",
    icon: <CheckCircleOutlined />,
    gradient: "linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%)",
    darkGradient: "linear-gradient(135deg, #0d2818 0%, #14361e 100%)",
    color: "#52c41a",
  },
];

function StatCard({
  label, value, icon, gradient, darkGradient, color, delay,
}: {
  label: string; value?: number; icon: React.ReactNode;
  gradient: string; darkGradient: string; color: string; delay: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay, ease: [0.25, 1, 0.5, 1] }}
      style={{
        background: gradient,
        borderRadius: 20,
        padding: "20px 22px",
        display: "flex",
        alignItems: "center",
        gap: 16,
        flex: 1,
        minWidth: 0,
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* 装饰圆 */}
      <div
        style={{
          position: "absolute",
          right: -16,
          top: -16,
          width: 80,
          height: 80,
          borderRadius: "50%",
          background: color,
          opacity: 0.08,
        }}
      />
      <div
        style={{
          width: 48,
          height: 48,
          borderRadius: 14,
          background: color,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 22,
          color: "#fff",
          flexShrink: 0,
        }}
      >
        {icon}
      </div>
      <div style={{ position: "relative", zIndex: 1 }}>
        <div style={{ fontSize: 32, fontWeight: 800, color, lineHeight: 1.1 }}>
          {value !== undefined ? value : <Skeleton.Input active size="small" style={{ width: 32, height: 28 }} />}
        </div>
        <div style={{ fontSize: 13, color: "#8c8c8c", marginTop: 2, fontWeight: 500 }}>
          {label}
        </div>
      </div>
    </motion.div>
  );
}

/* ── 今日任务行 ── */

function TodayTaskRow({ task, delay }: { task: TaskType; delay: number }) {
  const navigate = useNavigate();
  const isDone = task.status === "done";
  const priorityColors: Record<string, string> = { high: "#f5222d", medium: "#fa8c16", low: "#52c41a" };
  const bar = priorityColors[task.priority] || "#d9d9d9";

  return (
    <motion.div
      initial={{ opacity: 0, x: -12 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.3, delay, ease: [0.25, 1, 0.5, 1] }}
      onClick={() => navigate(`/tasks/${task.id}`)}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "14px 16px",
        background: "#fff",
        borderRadius: 14,
        cursor: "pointer",
        border: "1px solid #f0f0f0",
        transition: "box-shadow 0.2s, transform 0.2s",
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLDivElement).style.boxShadow = "0 2px 12px rgba(0,0,0,0.06)";
        (e.currentTarget as HTMLDivElement).style.transform = "translateX(4px)";
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLDivElement).style.boxShadow = "none";
        (e.currentTarget as HTMLDivElement).style.transform = "translateX(0)";
      }}
    >
      {/* 左侧色条 */}
      <div style={{ width: 4, height: 36, borderRadius: 2, background: bar, flexShrink: 0 }} />
      {/* 内容 */}
      <span
        style={{
          flex: 1,
          fontSize: 15,
          color: isDone ? "#bbb" : "#333",
          textDecoration: isDone ? "line-through" : "none",
          fontWeight: isDone ? 400 : 500,
        }}
      >
        {task.title}
      </span>
      {/* 类型标签 */}
      <span style={{
        fontSize: 11,
        color: "#999",
        background: "#f5f5f5",
        padding: "2px 8px",
        borderRadius: 8,
        flexShrink: 0,
      }}>
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

  const trendData =
    trend?.daily_completed.map((d) => ({
      date: d.date.slice(5),
      count: d.count,
    })) ?? [];

  /* 今日相关的任务：每日任务 + 短期未完成 + 长期进行中 */
  const todayTasks = (allTasks || [])
    .filter((t) => t.status !== "done")
    .sort((a, b) => {
      const p = { high: 0, medium: 1, low: 2 };
      return (p[a.priority] ?? 1) - (p[b.priority] ?? 1);
    })
    .slice(0, 5);

  const hasTrend = trendData.length > 0 && trendData.some((d) => d.count > 0);

  return (
    <div style={{ maxWidth: 720, margin: "0 auto", paddingTop: 12 }}>
      {/* ── 统计卡片 ── */}
      <div
        style={{
          display: "flex",
          gap: 14,
          flexWrap: "wrap",
        }}
      >
        {statCards.map((s, i) => (
          <StatCard
            key={s.key}
            label={s.label}
            value={overview?.by_status?.[s.key] as number | undefined}
            icon={s.icon}
            gradient={s.gradient}
            darkGradient={s.darkGradient}
            color={s.color}
            delay={i * 0.06}
          />
        ))}
      </div>

      {/* ── 今日待办 ── */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.2, ease: [0.25, 1, 0.5, 1] }}
        style={{ marginTop: 28 }}
      >
        <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 14 }}>
          <h3 style={{ fontSize: 17, fontWeight: 700, color: "#1a1a1a", margin: 0 }}>
            今日待办
          </h3>
          <span
            style={{ fontSize: 13, color: "#1677ff", cursor: "pointer", fontWeight: 500 }}
            onClick={() => navigate("/tasks")}
          >
            查看全部 →
          </span>
        </div>

        {todayTasks.length === 0 ? (
          <div
            style={{
              textAlign: "center",
              padding: "40px 20px",
              background: "#fff",
              borderRadius: 20,
              border: "1px solid #f0f0f0",
            }}
          >
            <div style={{ fontSize: 40, marginBottom: 12, opacity: 0.4 }}>🎯</div>
            <div style={{ fontSize: 15, color: "#999", marginBottom: 6 }}>今天没有待办任务</div>
            <div style={{ fontSize: 13, color: "#bbb" }}>点击右下角 + 按钮创建一个吧</div>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {todayTasks.map((t, i) => (
              <TodayTaskRow key={t.id} task={t} delay={0.25 + i * 0.04} />
            ))}
          </div>
        )}
      </motion.div>

      {/* ── 完成趋势 ── */}
      {hasTrend && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.4, ease: [0.25, 1, 0.5, 1] }}
          style={{
            marginTop: 28,
            background: "#fff",
            borderRadius: 20,
            border: "1px solid #f0f0f0",
            padding: "20px 22px",
          }}
        >
          <h3 style={{ fontSize: 17, fontWeight: 700, color: "#1a1a1a", margin: "0 0 8px" }}>
            完成趋势
          </h3>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={trendData}>
              <XAxis dataKey="date" tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis allowDecimals={false} tick={{ fontSize: 11 }} axisLine={false} tickLine={false} width={28} />
              <Tooltip
                contentStyle={{
                  borderRadius: 10,
                  border: "1px solid #f0f0f0",
                  boxShadow: "0 4px 16px rgba(0,0,0,0.06)",
                  fontSize: 13,
                }}
              />
              <Line
                type="monotone"
                dataKey="count"
                name="完成"
                stroke="#1677ff"
                strokeWidth={2.5}
                dot={{ r: 0 }}
                activeDot={{ r: 5, fill: "#1677ff", stroke: "#fff", strokeWidth: 2 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </motion.div>
      )}

      {/* ── 全部任务栏 ── */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.45, ease: [0.25, 1, 0.5, 1] }}
        style={{
          marginTop: 28,
          background: "#fff",
          borderRadius: 20,
          border: "1px solid #f0f0f0",
          overflow: "hidden",
        }}
      >
        <h3 style={{ fontSize: 17, fontWeight: 700, color: "#1a1a1a", margin: 0, padding: "20px 22px 8px" }}>
          全部任务
        </h3>
        <TaskBoard tasks={allTasks || []} />
      </motion.div>
    </div>
  );
}
