import { useFilterStore } from "../store/filterStore";

const filterGroups = [
  {
    key: "status" as const,
    label: "状态",
    setter: (s: typeof useFilterStore.getState) => s.setStatus,
    getter: (s: typeof useFilterStore.getState) => s.status,
    options: [
      { value: "", label: "全部" },
      { value: "todo", label: "待办" },
      { value: "in_progress", label: "进行中" },
      { value: "done", label: "已完成" },
    ],
  },
  {
    key: "priority" as const,
    label: "优先级",
    setter: (s: typeof useFilterStore.getState) => s.setPriority,
    getter: (s: typeof useFilterStore.getState) => s.priority,
    options: [
      { value: "", label: "全部" },
      { value: "high", label: "高" },
      { value: "medium", label: "中" },
      { value: "low", label: "低" },
    ],
  },
  {
    key: "tag" as const,
    label: "标签",
    setter: (s: typeof useFilterStore.getState) => s.setTag,
    getter: (s: typeof useFilterStore.getState) => s.tag,
    options: [
      { value: "", label: "全部" },
      { value: "学习", label: "学习" },
      { value: "工作", label: "工作" },
      { value: "生活", label: "生活" },
    ],
  },
];

export default function TaskFilterBar() {
  const store = useFilterStore();

  return (
    <div style={{ display: "flex", gap: 24, marginBottom: 16, alignItems: "center" }}>
      {filterGroups.map((g) => {
        const current = g.getter(store);
        return (
          <div key={g.key} style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ fontSize: 12, color: "#999", fontWeight: 500, flexShrink: 0 }}>{g.label}</span>
            <div style={{ display: "flex", gap: 4, background: "#f5f5f5", borderRadius: 10, padding: 3 }}>
              {g.options.map((o) => {
                const active = (o.value === "" && !current) || o.value === current;
                return (
                  <button
                    key={o.value}
                    onClick={() => {
                      if (g.key === "status") g.setter(store)(o.value || null);
                      else if (g.key === "priority") g.setter(store)(o.value || null);
                      else if (g.key === "tag") g.setter(store)(o.value || null);
                    }}
                    style={{
                      border: "none",
                      background: active ? "#fff" : "transparent",
                      color: active ? "#333" : "#999",
                      fontSize: 12,
                      fontWeight: active ? 600 : 400,
                      padding: "5px 14px",
                      borderRadius: 8,
                      cursor: "pointer",
                      boxShadow: active ? "0 1px 3px rgba(0,0,0,0.08)" : "none",
                      transition: "all 0.15s",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {o.label}
                  </button>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
