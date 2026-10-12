/** 按持久化 sequence 展示可回放的稳定事件，不依赖到达顺序。 */

import { Alert, Empty, Timeline, Typography } from "antd";
import ToolCallCard from "./ToolCallCard";
import type { AgentEvent } from "../../types/agent";

function asText(value: unknown): string {
  return typeof value === "string" ? value : JSON.stringify(value ?? "");
}

function content(event: AgentEvent) {
  if (event.type === "plan.updated") {
    const items = event.data.items;
    return <><Typography.Text strong>计划已更新</Typography.Text><ol className="agent-plan-list">{Array.isArray(items) && items.map((item, index) => <li key={index}>{asText(item)}</li>)}</ol></>;
  }
  if (event.type.startsWith("tool.")) return <ToolCallCard event={event} />;
  if (event.type === "approval.required") return <Typography.Text>需要审批：{asText(event.data.tool_name)}</Typography.Text>;
  if (event.type === "approval.resolved") return <Typography.Text>审批已处理：{asText(event.data.decision)}</Typography.Text>;
  if (event.type === "run.failed" || event.type === "run.interrupted") return <Alert type="error" showIcon message={asText(event.data.message ?? event.data.error_code)} />;
  if (event.type === "run.started") return <Typography.Text>运行已开始</Typography.Text>;
  if (event.type === "run.completed") return <Typography.Text>运行已完成</Typography.Text>;
  if (event.type === "run.cancelled") return <Typography.Text>运行已取消</Typography.Text>;
  if (event.type === "model.delta") return <Typography.Text type="secondary">{asText(event.data.text ?? event.data.delta)}</Typography.Text>;
  return <><Typography.Text>其他事件</Typography.Text><Typography.Text type="secondary" style={{ marginLeft: 8 }}>{event.type}</Typography.Text></>;
}

export default function RunTimeline({ events }: { events: AgentEvent[] }) {
  if (!events.length) return <Empty description="运行事件将在这里出现" image={Empty.PRESENTED_IMAGE_SIMPLE} />;
  return <Timeline className="agent-timeline" items={[...events]
    .sort((a, b) => a.sequence - b.sequence)
    .map((event) => ({
      color: event.type.endsWith("failed") ? "red" : event.type === "approval.required" ? "orange" : "blue",
      content: <div className="agent-timeline-entry">
        <div className="agent-timeline-meta"><span>#{String(event.sequence).padStart(2, "0")}</span><time>{new Date(event.created_at).toLocaleTimeString("zh-CN")}</time></div>
        {content(event)}
      </div>,
    }))} />;
}
