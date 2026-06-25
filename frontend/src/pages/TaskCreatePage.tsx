import { ArrowLeftOutlined } from "@ant-design/icons";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { App, Button } from "antd";
import { useNavigate } from "react-router-dom";
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
            await createTask({
              title: st.title,
              priority: st.priority,
              task_type: "short_term",
              parent_id: created.id,
            });
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
    <>
      <Button
        type="primary"
        icon={<ArrowLeftOutlined />}
        onClick={() => navigate("/tasks")}
        style={{ marginBottom: 24, borderRadius: 6 }}
      >
        返回
      </Button>
      <h2 style={{ marginBottom: 24, fontSize: 18, fontWeight: 600 }}>新建任务</h2>
      <TaskForm
        onSubmit={(values) => mutation.mutate(values)}
        onCancel={() => navigate("/tasks")}
        loading={mutation.isPending}
      />
    </>
  );
}
