import { useQuery } from "@tanstack/react-query";
import { Card, Col, Row, Tag, Typography } from "antd";
import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { motion } from "framer-motion";
import client from "../api/client";
import TaskBoard from "../components/ui/agent-plan";
import { fetchTasks } from "../api/tasks";

interface Overview {
  total: number;
  by_status: Record<string, number>;
  by_priority: Record<string, number>;
}

interface Trend {
  daily_completed: { date: string; count: number }[];
}

const PRIORITY_COLORS: Record<string, string> = {
  high: "#f5222d",
  medium: "#faad14",
  low: "#52c41a",
};

const PRIORITY_LABEL: Record<string, string> = {
  high: "高",
  medium: "中",
  low: "低",
};

export default function DashboardPage() {
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

  return (
    <>
      <Typography.Title level={4} style={{ marginBottom: 24, marginTop: 0 }}>
        仪表盘
      </Typography.Title>

      {/* 统计区 — 一行三列数字，克制无装饰 */}
      <Row gutter={[24, 16]} style={{ marginBottom: 8 }}>
        {[
          { label: "总任务", value: overview?.total ?? 0, color: "#1677ff" },
          { label: "待办", value: overview?.by_status.todo ?? 0, color: "#faad14" },
          { label: "已完成", value: overview?.by_status.done ?? 0, color: "#52c41a" },
        ].map((s, i) => (
          <Col xs={24} sm={8} key={s.label}>
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, delay: i * 0.08, ease: [0.25, 1, 0.5, 1] }}
              style={{ display: "flex", alignItems: "baseline", gap: 6 }}
            >
              <motion.span
                style={{ fontSize: 36, fontWeight: 700, color: s.color, lineHeight: 1 }}
                initial={{ opacity: 0, scale: 0.5 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.4, delay: i * 0.08 + 0.1, ease: [0.34, 1.56, 0.64, 1] }}
              >
                {s.value}
              </motion.span>
              <span style={{ fontSize: 14, color: "#8c8c8c" }}>{s.label}</span>
            </motion.div>
          </Col>
        ))}
      </Row>

      {/* 优先级 Tags — 紧贴统计下方 */}
      {overview && (
        <div style={{ marginBottom: 24 }}>
          {Object.entries(overview.by_priority)
            .filter(([, v]) => v > 0)
            .map(([k, v]) => (
              <Tag key={k} color={PRIORITY_COLORS[k]} style={{ marginRight: 4 }}>
                {PRIORITY_LABEL[k]} {v}
              </Tag>
            ))}
        </div>
      )}

      {/* 图表 + 任务栏 */}
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay: 0.25, ease: [0.25, 1, 0.5, 1] }}
          >
          <Card
            title="完成趋势"
            styles={{ body: { padding: "16px 20px 12px" } }}
          >
            {trendData.length > 0 && trendData.some((d) => d.count > 0) ? (
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={trendData}>
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{ borderRadius: 6, border: "1px solid #f0f0f0", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}
                  />
                  <Line
                    type="monotone"
                    dataKey="count"
                    name="完成"
                    stroke="#1677ff"
                    strokeWidth={2}
                    dot={{ r: 0 }}
                    activeDot={{ r: 4, fill: "#1677ff" }}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div
                style={{
                  height: 200,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "#bbb",
                  fontSize: 13,
                }}
              >
                完成一些任务后，这里会出现趋势图
              </div>
            )}
          </Card>
          </motion.div>
        </Col>

        <Col xs={24} lg={12}>
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay: 0.35, ease: [0.25, 1, 0.5, 1] }}
          >
          <Card
            title="任务栏"
            styles={{ body: { padding: 0, maxHeight: 340, overflow: "auto" } }}
          >
            <TaskBoard tasks={allTasks || []} />
          </Card>
          </motion.div>
        </Col>
      </Row>
    </>
  );
}
