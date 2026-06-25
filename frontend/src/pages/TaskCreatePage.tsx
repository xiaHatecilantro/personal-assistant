import { ArrowLeftOutlined } from "@ant-design/icons";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { App, Button } from "antd";
import { useNavigate } from "react-router-dom";
import { motion } from "motion/react";
import { createTask } from "../api/tasks";
import TaskForm, { type TaskFormValues } from "../components/TaskForm";

export default function TaskCreatePage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { message } = App.useApp();

  const mutation = useMutation({
    mutationFn: async (data: TaskFormValues) => {
      const { subtasks, ...parent } = data;
      const created = await createTask(parent);
      if (subtasks && subtasks.length > 0) {
        for (const st of subtasks) {
          if (st.title.trim()) {
            await createTask({ title: st.title, priority: st.priority, task_type: "short_term", parent_id: created.id });
          }
        }
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      message.success("任务创建成功");
      navigate("/tasks");
    },
  });

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.25, 1, 0.5, 1] }}
      style={{ maxWidth: 600, margin: "0 auto", paddingTop: 8 }}
    >
      <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate("/tasks")}
        style={{ marginBottom: 20, color: "#999", fontSize: 14 }}>
        返回
      </Button>
      <h2 style={{ fontSize: 22, fontWeight: 700, color: "#1a1a1a", margin: "0 0 28px" }}>新建任务</h2>
      <TaskForm
        onSubmit={(values) => mutation.mutate(values)}
        onCancel={() => navigate("/tasks")}
        loading={mutation.isPending}
      />
    </motion.div>
  );
}
