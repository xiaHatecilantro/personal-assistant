import { ArrowLeftOutlined, DeleteOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { App, Button, Popconfirm, Spin } from "antd";
import { useNavigate, useParams } from "react-router-dom";
import { createTask, deleteTask, fetchTask, fetchTasks, updateTask } from "../api/tasks";
import TaskForm, { type TaskFormValues } from "../components/TaskForm";

export default function TaskDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { message } = App.useApp();

  const {
    data: task,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["tasks", Number(id)],
    queryFn: () => fetchTask(Number(id)),
    enabled: !!id,
  });

  const { data: existingSubtasks } = useQuery({
    queryKey: ["tasks", "sub", Number(id)],
    queryFn: () => fetchTasks({ parent_id: Number(id) }),
    enabled: !!id && task?.task_type === "long_term",
  });

  const updateMutation = useMutation({
    mutationFn: async (data: TaskFormValues) => {
      const { subtasks, ...parent } = data;
      await updateTask(Number(id), parent);

      if (subtasks && subtasks.length > 0) {
        // 简单策略：删除旧子任务，重建新的
        if (existingSubtasks) {
          for (const st of existingSubtasks) {
            await deleteTask(st.id);
          }
        }
        for (const st of subtasks) {
          if (st.title.trim()) {
            await createTask({
              title: st.title,
              priority: st.priority,
              task_type: "short_term",
              parent_id: Number(id),
            });
          }
        }
      } else if (existingSubtasks && existingSubtasks.length > 0) {
        for (const st of existingSubtasks) {
          await deleteTask(st.id);
        }
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      message.success("任务已更新");
      navigate("/tasks");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async () => {
      if (existingSubtasks) {
        for (const st of existingSubtasks) {
          await deleteTask(st.id);
        }
      }
      await deleteTask(Number(id));
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      message.success("任务已删除");
      navigate("/tasks");
    },
  });

  if (isLoading) return <Spin />;
  if (isError || !task) return <div>任务不存在</div>;

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
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 24,
        }}
      >
        <h2 style={{ margin: 0, fontSize: 18, fontWeight: 600 }}>编辑任务</h2>
        <Popconfirm
          title="确定删除此任务？"
          onConfirm={() => deleteMutation.mutate()}
          okText="删除"
          cancelText="取消"
          okButtonProps={{ danger: true }}
        >
          <Button danger icon={<DeleteOutlined />} loading={deleteMutation.isPending}>
            删除
          </Button>
        </Popconfirm>
      </div>

      <TaskForm
        initialValues={task}
        initialSubtasks={
          existingSubtasks?.map((st) => ({
            title: st.title,
            priority: st.priority,
          })) || []
        }
        onSubmit={(values) => updateMutation.mutate(values)}
        onCancel={() => navigate("/tasks")}
        loading={updateMutation.isPending}
      />
    </>
  );
}
