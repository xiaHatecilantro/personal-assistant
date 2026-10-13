/** 模块职责：提供任务计划看板的独立页面入口。 */

import Plan from "../components/ui/agent-plan";

export default function PlanPage() {
  return (
    <div className="flex flex-col w-full h-full">
      <Plan tasks={[]} />
    </div>
  );
}
