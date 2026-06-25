import { Select, Space } from "antd";
import { useFilterStore } from "../store/filterStore";

export default function TaskFilterBar() {
  const { status, priority, tag, setStatus, setPriority, setTag } =
    useFilterStore();

  return (
    <Space style={{ marginBottom: 16 }}>
      <Select
        allowClear
        placeholder="全部状态"
        style={{ width: 130 }}
        value={status}
        onChange={(v) => setStatus(v || null)}
        options={[
          { value: "todo", label: "待办" },
          { value: "in_progress", label: "进行中" },
          { value: "done", label: "已完成" },
        ]}
      />
      <Select
        allowClear
        placeholder="全部优先级"
        style={{ width: 130 }}
        value={priority}
        onChange={(v) => setPriority(v || null)}
        options={[
          { value: "high", label: "高" },
          { value: "medium", label: "中" },
          { value: "low", label: "低" },
        ]}
      />
      <Select
        allowClear
        placeholder="全部标签"
        style={{ width: 130 }}
        value={tag}
        onChange={(v) => setTag(v || null)}
        options={[
          { value: "学习", label: "学习" },
          { value: "工作", label: "工作" },
          { value: "生活", label: "生活" },
        ]}
      />
    </Space>
  );
}
