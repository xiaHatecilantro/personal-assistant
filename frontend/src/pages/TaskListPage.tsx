import { DeleteOutlined, EditOutlined, PlusOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { App, Button, Empty, Popconfirm, Space, Spin, Table, Tabs, Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { deleteTask, fetchTasks } from "../api/tasks";
import TaskFilterBar from "../components/TaskFilterBar";
import TaskTimer from "../components/TaskTimer";
import { useFilterStore } from "../store/filterStore";
import type { Task } from "../types/task";

const PAGE_SIZE = 10;

const statusMap: Record<string, { color: string; text: string }> = {
  todo: { color: "default", text: "待办" },
  in_progress: { color: "processing", text: "进行中" },
  done: { color: "success", text: "已完成" },
};

const priorityMap: Record<string, { color: string; text: string }> = {
  high: { color: "red", text: "高" },
  medium: { color: "orange", text: "中" },
  low: { color: "green", text: "低" },
};

const typeLabel: Record<string, string> = {
  short_term: "短期",
  long_term: "长期",
  daily: "每日",
};

const typeColor: Record<string, string> = {
  short_term: "blue",
  long_term: "purple",
  daily: "green",
};

export default function TaskListPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { message } = App.useApp();
  const [activeTab, setActiveTab] = useState("short_term");
  const { status, priority, tag, page, setPage } = useFilterStore();

  const { data: allTasks, isLoading } = useQuery({
    queryKey: ["tasks", { task_type: activeTab, status, priority, tag }],
    queryFn: () => fetchTasks({ task_type: activeTab, status: status || undefined, priority: priority || undefined, tag: tag || undefined }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteTask(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      message.success("任务已删除");
    },
  });

  const tasks = allTasks || [];

  const columns: ColumnsType<Task> = [
    {
      title: "标题",
      dataIndex: "title",
      key: "title",
      ellipsis: true,
      render: (t: string, r) => (
        <span>
          <Tag color={typeColor[r.task_type]} style={{ marginRight: 6 }}>
            {typeLabel[r.task_type]}
          </Tag>
          {t}
        </span>
      ),
    },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      width: 100,
      render: (s: string) => (
        <Tag color={statusMap[s]?.color}>{statusMap[s]?.text || s}</Tag>
      ),
    },
    {
      title: "优先级",
      dataIndex: "priority",
      key: "priority",
      width: 80,
      render: (p: string) => (
        <Tag color={priorityMap[p]?.color}>{priorityMap[p]?.text || p}</Tag>
      ),
    },
    {
      title: "标签",
      dataIndex: "tag",
      key: "tag",
      width: 100,
      render: (t: string | null) =>
        t ? <Tag>{t}</Tag> : <span style={{ color: "#ccc" }}>—</span>,
    },
    ...(activeTab !== "daily"
      ? ([
          {
            title: "截止日期",
            dataIndex: "due_date",
            key: "due_date",
            width: 120,
            render: (d: string | null) => d || <span style={{ color: "#ccc" }}>—</span>,
          },
        ] as ColumnsType<Task>)
      : []),
    ...(activeTab === "daily"
      ? ([
          {
            title: "计时",
            key: "timer",
            width: 160,
            render: (_: unknown, record: Task) => <TaskTimer task={record} />,
          },
        ] as ColumnsType<Task>)
      : []),
    {
      title: "操作",
      key: "actions",
      width: 100,
      render: (_, record) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={(e) => {
              e.stopPropagation();
              navigate(`/tasks/${record.id}`);
            }}
          />
          <Popconfirm
            title="确定删除？"
            onConfirm={(e) => {
              e?.stopPropagation();
              deleteMutation.mutate(record.id);
            }}
            onCancel={(e) => e?.stopPropagation()}
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
          >
            <Button
              type="link"
              danger
              size="small"
              icon={<DeleteOutlined />}
              onClick={(e) => e.stopPropagation()}
            />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 16,
        }}
      >
        <Typography.Title level={4} style={{ margin: 0 }}>
          任务列表
        </Typography.Title>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => navigate("/tasks/new")}
        >
          新建任务
        </Button>
      </div>

      <Tabs
        activeKey={activeTab}
        onChange={(key) => setActiveTab(key)}
        items={[
          { key: "short_term", label: "短期任务" },
          { key: "long_term", label: "长期任务" },
          { key: "daily", label: "每日任务" },
        ]}
      />

      <TaskFilterBar />

      <Spin spinning={isLoading}>
        <Table<Task>
          columns={columns}
          dataSource={tasks}
          rowKey="id"
          onRow={(record) => ({
            onClick: () => navigate(`/tasks/${record.id}`),
            style: { cursor: "pointer" },
          })}
          locale={{
            emptyText: (
              <Empty
                description={
                  activeTab === "daily"
                    ? "点击「新建任务」，任务类型选「每日任务」"
                    : activeTab === "long_term"
                      ? "点击「新建任务」，任务类型选「长期任务」"
                      : "点击「新建任务」创建第一个短期任务"
                }
              />
            ),
          }}
          pagination={{
            current: page,
            pageSize: PAGE_SIZE,
            total: tasks.length,
            onChange: (p) => setPage(p),
            showSizeChanger: false,
          }}
        />
      </Spin>
    </>
  );
}
