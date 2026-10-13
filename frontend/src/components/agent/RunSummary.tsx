/** 最终状态完全取自服务端 Run 快照，刷新后仍可还原。 */

import { Alert, Descriptions, Typography } from "antd";
import type { RunDetail } from "../../types/agent";

export default function RunSummary({ run, toolCount }: { run: RunDetail; toolCount: number }) {
  const duration = run.started_at && run.finished_at
    ? Math.max(0, Math.round((Date.parse(run.finished_at) - Date.parse(run.started_at)) / 1000))
    : null;
  return <section className="agent-summary" aria-label="运行摘要">
    <Typography.Text className="agent-eyebrow">RUN SUMMARY / 运行摘要</Typography.Text>
    <Typography.Title level={4} style={{ margin: "8px 0 16px" }}>执行结果</Typography.Title>
    {run.status === "completed" && <Typography.Paragraph className="agent-answer">{run.final_answer || "运行完成，暂无文字摘要。"}</Typography.Paragraph>}
    {run.status === "failed" && <Alert type="error" showIcon message={run.error_message || "执行失败"} description={run.error_code || undefined} />}
    {run.status === "cancelled" && <Alert type="warning" showIcon message="运行已取消" />}
    <Descriptions size="small" column={{ xs: 1, sm: 3 }} items={[
      { key: "steps", label: "步骤", children: run.step_count },
      { key: "tools", label: "工具事件", children: toolCount },
      { key: "duration", label: "耗时", children: duration === null ? "—" : `${duration} 秒` },
    ]} />
  </section>;
}
