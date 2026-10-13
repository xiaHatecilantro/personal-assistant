/** 工具事件只渲染结构化数据，避免把模型或工具内容作为 HTML 注入。 */

import { Alert, Descriptions, Tag, Typography } from "antd";
import type { AgentEvent } from "../../types/agent";

function display(value: unknown): string {
  if (typeof value === "string") return value;
  if (value === undefined || value === null) return "—";
  return JSON.stringify(value, null, 2);
}

export default function ToolCallCard({ event }: { event: AgentEvent }) {
  const status = event.type.split(".")[1];
  const { tool_name, tool_call_id, arguments: args, result, error } = event.data;
  return (
    <div className="agent-tool-card">
      <div className="agent-tool-head">
        <Typography.Text strong>{display(tool_name)}</Typography.Text>
        <Tag color={status === "failed" ? "error" : status === "completed" ? "success" : "processing"}>
          {status === "proposed" ? "待执行" : status === "started" ? "执行中" : status === "completed" ? "已完成" : "失败"}
        </Tag>
      </div>
      <Descriptions size="small" column={1} items={[
        { key: "id", label: "调用 ID", children: <code>{display(tool_call_id)}</code> },
        ...(args !== undefined ? [{ key: "args", label: "输入", children: <pre className="agent-json">{display(args)}</pre> }] : []),
        ...(result !== undefined ? [{ key: "result", label: "观察", children: <pre className="agent-json">{display(result)}</pre> }] : []),
      ]} />
      {error !== undefined && <Alert type="error" showIcon message={display(error)} />}
    </div>
  );
}
