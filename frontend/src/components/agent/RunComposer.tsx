/** 创建 Run 的输入边界与提交状态。 */

import { ArrowRightOutlined } from "@ant-design/icons";
import { Button, Input, Typography } from "antd";
import { useState } from "react";

export default function RunComposer({ onSubmit, submitting }: {
  onSubmit: (goal: string) => void;
  submitting: boolean;
}) {
  const [goal, setGoal] = useState("");
  const normalized = goal.trim();
  return (
    <section className="agent-composer" aria-label="新建 Agent 运行">
      <div className="agent-composer-heading">
        <div>
          <Typography.Text className="agent-eyebrow">NEW RUN / 新建运行</Typography.Text>
          <Typography.Title level={3} style={{ margin: "8px 0 4px" }}>告诉 Agent 你想完成什么</Typography.Title>
          <Typography.Text type="secondary">它会规划步骤；写入任务或笔记前，会请你确认。</Typography.Text>
        </div>
      </div>
      <Input.TextArea
        aria-label="Agent 目标"
        value={goal}
        onChange={(event) => setGoal(event.target.value)}
        placeholder="例如：整理本周未完成的任务，并提出三项优先行动"
        maxLength={4000}
        showCount
        autoSize={{ minRows: 3, maxRows: 6 }}
        disabled={submitting}
      />
      <div className="agent-composer-footer">
        <Typography.Text type="secondary">执行过程和结果会保存在运行记录中</Typography.Text>
        <Button type="primary" icon={<ArrowRightOutlined />} iconPlacement="end"
          disabled={!normalized} loading={submitting} onClick={() => onSubmit(normalized)}>
          开始执行
        </Button>
      </div>
    </section>
  );
}
