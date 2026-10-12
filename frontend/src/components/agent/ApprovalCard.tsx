/** 审批在用户显式二次确认后提交，revision 由服务端 CAS 校验。 */

import { Alert, Button, Input, Space, Tag, Typography } from "antd";
import { useState } from "react";
import type { ApprovalDecision, ApprovalSummary } from "../../types/agent";

type Action = "approve" | "reject" | "edit";

export default function ApprovalCard({ approval, submitting, onDecision }: {
  approval: ApprovalSummary;
  submitting: boolean;
  onDecision: (decision: ApprovalDecision) => void;
}) {
  const [action, setAction] = useState<Action | null>(null);
  const [argumentsText, setArgumentsText] = useState(() => JSON.stringify(approval.arguments, null, 2));
  const [validationError, setValidationError] = useState("");
  const pending = approval.status === "pending";

  function confirm() {
    if (!pending || submitting || !action) return;
    if (action === "edit") {
      try {
        const value: unknown = JSON.parse(argumentsText);
        if (!value || Array.isArray(value) || typeof value !== "object") throw new Error("参数必须是 JSON 对象");
        onDecision({ decision: "edit", revision: approval.revision, edited_arguments: value as Record<string, unknown> });
        setValidationError("");
      } catch {
        setValidationError("请输入合法的 JSON 对象");
      }
      return;
    }
    onDecision({ decision: action, revision: approval.revision });
  }

  return <section className="agent-approval-card" aria-label={`${approval.tool_name} 审批`}>
    <div className="agent-tool-head"><div><Typography.Text strong>{approval.tool_name}</Typography.Text><Typography.Text type="secondary" style={{ display: "block", fontSize: 12 }}>调用 {approval.tool_call_id}</Typography.Text></div><Tag color={pending ? "warning" : "default"}>{pending ? "等待你的决定" : "已处理"}</Tag></div>
    <Typography.Text type="secondary">拟执行参数</Typography.Text>
    <pre className="agent-json agent-approval-arguments">{JSON.stringify(approval.arguments, null, 2)}</pre>
    {pending && <>
      {!action && <Space wrap><Button aria-label="批准" type="primary" disabled={submitting} onClick={() => setAction("approve")}>批准</Button><Button disabled={submitting} onClick={() => setAction("edit")}>编辑后批准</Button><Button aria-label="拒绝" danger disabled={submitting} onClick={() => setAction("reject")}>拒绝</Button></Space>}
      {action && <div className="agent-approval-confirm">
        <Alert type="warning" showIcon message={action === "reject" ? "确认拒绝这次写操作？" : "请核对操作和参数后确认。"} />
        {action === "edit" && <Input.TextArea aria-label="编辑工具参数" value={argumentsText} onChange={(event) => { setArgumentsText(event.target.value); setValidationError(""); }} autoSize={{ minRows: 4, maxRows: 10 }} />}
        {validationError && <Typography.Text type="danger">{validationError}</Typography.Text>}
        <Space><Button type={action === "reject" ? "default" : "primary"} danger={action === "reject"} loading={submitting} onClick={confirm}>{action === "edit" ? "确认提交编辑" : action === "approve" ? "确认批准" : "确认拒绝"}</Button><Button disabled={submitting} onClick={() => setAction(null)}>返回</Button></Space>
      </div>}
    </>}
  </section>;
}
