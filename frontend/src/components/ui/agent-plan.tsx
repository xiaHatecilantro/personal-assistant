import { useQuery } from "@tanstack/react-query";
import { motion, AnimatePresence } from "motion/react";
import { useState } from "react";
import { fetchTasks } from "../../api/tasks";
import type { Task as TaskType } from "../../types/task";

interface Props {
  tasks: TaskType[];
}

const ORDER = ["in_progress", "todo", "done"] as const;

const DOT: Record<string, string> = {
  in_progress: "bg-blue-500",
  todo: "bg-gray-300",
  done: "bg-emerald-500",
};

const STATUS_LABEL: Record<string, string> = {
  in_progress: "进行中",
  todo: "待办",
  done: "已完成",
};

const PRIORITY: Record<string, { label: string; cls: string }> = {
  high: { label: "高优", cls: "text-red-500" },
  medium: { label: "中优", cls: "text-orange-500" },
  low: { label: "低优", cls: "text-green-500" },
};

const TASK_TYPE: Record<string, { label: string; cls: string }> = {
  short_term: { label: "短期", cls: "text-blue-500" },
  long_term: { label: "长期", cls: "text-purple-500" },
  daily: { label: "每日", cls: "text-cyan-500" },
};

export default function TaskBoard({ tasks }: Props) {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  const grouped: Record<string, TaskType[]> = { todo: [], in_progress: [], done: [] };
  for (const t of tasks) {
    if (grouped[t.status]) grouped[t.status].push(t);
  }

  const toggleSection = (k: string) =>
    setCollapsed((p) => {
      const n = new Set(p);
      n.has(k) ? n.delete(k) : n.add(k);
      return n;
    });

  return (
    <div className="flex flex-col">
      {ORDER.map((key, idx) => {
        const items = grouped[key] || [];
        const closed = collapsed.has(key);

        return (
          <div key={key}>

            {/* 分组头 */}
            <button
              onClick={() => toggleSection(key)}
              className="w-full flex items-center gap-2.5 px-4 py-3 text-left select-none hover:bg-gray-50/50 transition-colors"
            >
              <span className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${DOT[key]}`} />
              <span className="text-[15px] text-gray-700 font-semibold">
                {STATUS_LABEL[key]}
              </span>
              <span className="text-[13px] text-gray-400 tabular-nums">{items.length}</span>
              <svg
                className={`ml-auto w-3.5 h-3.5 text-gray-300 transition-transform duration-150 ${closed ? "-rotate-90" : ""}`}
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
              >
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </button>

            <AnimatePresence initial={false}>
              {!closed && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.18, ease: [0.4, 0, 0.2, 1] }}
                  className="overflow-hidden"
                >
                  <div className="pb-3">
                    {items.length === 0 ? (
                      <p className="px-4 py-4 text-[14px] text-gray-400">
                        {key === "todo"
                          ? "还没有待办任务"
                          : key === "in_progress"
                            ? "还没有进行中的任务"
                            : "还没有已完成的任务"}
                      </p>
                    ) : (
                      <div className="flex flex-col gap-1.5">
                        {items.map((task, i) => (
                          <motion.div
                            key={task.id}
                            initial={{ opacity: 0, x: -8 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ duration: 0.2, delay: i * 0.03, ease: [0.25, 1, 0.5, 1] }}
                          >
                          <TaskRow
                            task={task}
                            open={expanded.has(task.id)}
                            onToggle={() =>
                              setExpanded((p) => {
                                const n = new Set(p);
                                n.has(task.id) ? n.delete(task.id) : n.add(task.id);
                                return n;
                              })
                            }
                          />
                          </motion.div>
                        ))}
                      </div>
                    )}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        );
      })}
    </div>
  );
}

/* ---- 任务行 ---- */
function TaskRow({
  task,
  open,
  onToggle,
}: {
  task: TaskType;
  open: boolean;
  onToggle: () => void;
}) {
  const isLong = task.task_type === "long_term";
  const isDone = task.status === "done";
  const prio = PRIORITY[task.priority] || PRIORITY.medium;
  const type = TASK_TYPE[task.task_type] || TASK_TYPE.short_term;

  const { data: subs } = useQuery({
    queryKey: ["tasks", "sub", task.id],
    queryFn: () => fetchTasks({ parent_id: task.id }),
    enabled: open,
    staleTime: 30_000,
  });

  return (
    <div>
      <motion.div
        className={`group flex items-center gap-3 mx-2 px-2.5 py-3 rounded-md cursor-pointer transition-colors ${
          isDone ? "hover:bg-gray-50/40" : "hover:bg-gray-50/80"
        }`}
        whileHover={{ backgroundColor: isDone ? "rgba(0,0,0,0.02)" : "rgba(0,0,0,0.035)" }}
        transition={{ duration: 0.1 }}
        onClick={isLong ? onToggle : undefined}
      >
        {/* 左侧标题 */}
        <div className="flex-1 min-w-0 flex items-center gap-2">
          {isLong && (
            <svg
              className={`flex-shrink-0 w-3 h-3 text-gray-300 transition-transform duration-150 ${open ? "rotate-90" : ""}`}
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
            >
              <polyline points="9 6 15 12 9 18" />
            </svg>
          )}
          <span
            className={`text-[15px] leading-relaxed truncate ${
              isDone ? "text-gray-400 line-through" : "text-gray-800"
            }`}
          >
            {task.title}
          </span>
        </div>

        {/* 右侧元信息 */}
        <div className="flex-shrink-0 flex items-center gap-1.5">
          {task.due_date && (
            <span className="text-[13px] text-gray-400 tabular-nums">
              {task.due_date.slice(5)}
            </span>
          )}
          <span className={`text-[13px] font-medium ${type.cls}`}>
            {type.label}
          </span>
          <span className={`text-[13px] font-medium ${prio.cls}`}>
            {prio.label}
          </span>
          {task.tag && (
            <span className="text-[13px] text-gray-400 font-medium">
              {task.tag}
            </span>
          )}
        </div>
      </motion.div>

      {/* 子任务树 */}
      <AnimatePresence initial={false}>
        {open && isLong && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.18, ease: [0.4, 0, 0.2, 1] }}
            className="overflow-hidden"
          >
              <div className="ml-7 py-1">
              {subs && subs.length > 0 ? (
                subs.map((st) => {
                  const sp = PRIORITY[st.priority] || PRIORITY.medium;
                  const stdone = st.status === "done";
                  return (
                    <div
                      key={st.id}
                      className={`flex items-center gap-2.5 px-2 py-2 rounded hover:bg-gray-50/60 transition-colors ${
                        stdone ? "text-gray-400" : "text-gray-600"
                      }`}
                    >
                      <span
                        className={`text-[14px] flex-1 truncate ${stdone ? "line-through" : ""}`}
                      >
                        {st.title}
                      </span>
                      <span className={`text-[13px] font-medium ${sp.cls}`}>
                        {sp.label}
                      </span>
                      {st.tag && (
                        <span className="text-[13px] text-gray-400 font-medium">
                          {st.tag}
                        </span>
                      )}
                    </div>
                  );
                })
              ) : (
                <p className="text-[13px] text-gray-300 py-2">点击添加子任务</p>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
