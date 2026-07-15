import { MinusCircleOutlined, PlusOutlined } from "@ant-design/icons";
import { Button, DatePicker, Form, Input, InputNumber, Select, Space } from "antd";
import { useEffect, useState } from "react";
import type { Task } from "../types/task";

export interface SubTaskItem {
  title: string;
  priority: string;
}

export interface TaskFormValues {
  title: string;
  description?: string | null;
  priority: string;
  status: string;
  due_date?: string | null;
  tag?: string | null;
  task_type: string;
  deadline_precision?: string | null;
  timer_preset?: number | null;
  subtasks?: SubTaskItem[];
}

interface Props {
  initialValues?: Task;
  initialSubtasks?: SubTaskItem[];
  onSubmit: (values: TaskFormValues) => void;
  onCancel: () => void;
  loading?: boolean;
}

export default function TaskForm({ initialValues, initialSubtasks, onSubmit, onCancel, loading }: Props) {
  const [form] = Form.useForm<TaskFormValues>();
  const [taskType, setTaskType] = useState(initialValues?.task_type || "short_term");

  useEffect(() => {
    if (initialValues) {
      form.setFieldsValue({
        title: initialValues.title,
        description: initialValues.description,
        priority: initialValues.priority,
        status: initialValues.status,
        due_date: initialValues.due_date || null,
        tag: initialValues.tag,
        task_type: initialValues.task_type,
        deadline_precision: initialValues.deadline_precision,
        timer_preset: initialValues.timer_preset,
        subtasks: initialSubtasks || [],
      });
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setTaskType(initialValues.task_type);
    }
  }, [initialValues, initialSubtasks, form]);

  return (
    <Form
      form={form}
      layout="vertical"
      onFinish={onSubmit}
      initialValues={{
        task_type: "short_term",
        priority: "medium",
        status: "todo",
        subtasks: [],
      }}
      style={{ maxWidth: 560, background: "#fff", borderRadius: 20, border: "1px solid #f0f0f0", padding: "28px 28px 12px" }}
    >
      <Form.Item
        name="title"
        label="标题"
        rules={[{ required: true, message: "请输入任务标题" }, { max: 200 }]}
      >
        <Input placeholder="输入任务标题" />
      </Form.Item>

      <Form.Item name="description" label="描述">
        <Input.TextArea rows={2} placeholder="任务详细描述（可选）" />
      </Form.Item>

      <Form.Item name="task_type" label="任务类型" rules={[{ required: true }]}>
        <Select style={{ width: 200 }} onChange={(v) => setTaskType(v)}>
          <Select.Option value="short_term">短期任务</Select.Option>
          <Select.Option value="long_term">长期任务</Select.Option>
          <Select.Option value="daily">每日任务</Select.Option>
        </Select>
      </Form.Item>

      <Space size="middle">
        <Form.Item name="priority" label="优先级" rules={[{ required: true }]}>
          <Select style={{ width: 140 }}>
            <Select.Option value="high">高</Select.Option>
            <Select.Option value="medium">中</Select.Option>
            <Select.Option value="low">低</Select.Option>
          </Select>
        </Form.Item>

        <Form.Item name="status" label="状态" rules={[{ required: true }]}>
          <Select style={{ width: 140 }}>
            <Select.Option value="todo">待办</Select.Option>
            <Select.Option value="in_progress">进行中</Select.Option>
            <Select.Option value="done">已完成</Select.Option>
          </Select>
        </Form.Item>
      </Space>

      {taskType === "short_term" && (
        <Form.Item name="due_date" label="截止日期">
          <DatePicker style={{ width: 200 }} placeholder="选择日期" />
        </Form.Item>
      )}

      {taskType === "long_term" && (
        <>
          <Space size="middle" align="start">
            <Form.Item name="due_date" label="截止日期">
              <DatePicker style={{ width: 200 }} placeholder="选择日期" />
            </Form.Item>
            <Form.Item name="deadline_precision" label="精度">
              <Select style={{ width: 120 }}>
                <Select.Option value="day">精确到天</Select.Option>
                <Select.Option value="month">精确到月</Select.Option>
                <Select.Option value="year">精确到年</Select.Option>
              </Select>
            </Form.Item>
          </Space>

          {/* 子任务 */}
          <Form.Item label="子任务">
            <Form.List name="subtasks">
              {(fields, { add, remove }) => (
                <>
                  {fields.map(({ key, name }) => (
                    <Space key={key} align="start" style={{ display: "flex", marginBottom: 8 }}>
                      <Form.Item name={[name, "title"]} rules={[{ required: true, message: "子任务标题必填" }]} noStyle>
                        <Input placeholder="子任务标题" style={{ width: 260 }} />
                      </Form.Item>
                      <Form.Item name={[name, "priority"]} initialValue="medium" noStyle>
                        <Select style={{ width: 100 }}>
                          <Select.Option value="high">高</Select.Option>
                          <Select.Option value="medium">中</Select.Option>
                          <Select.Option value="low">低</Select.Option>
                        </Select>
                      </Form.Item>
                      <Button
                        type="text"
                        danger
                        icon={<MinusCircleOutlined />}
                        onClick={() => remove(name)}
                      />
                    </Space>
                  ))}
                  <Button
                    type="dashed"
                    onClick={() => add({ title: "", priority: "medium" })}
                    icon={<PlusOutlined />}
                    block
                  >
                    添加子任务
                  </Button>
                </>
              )}
            </Form.List>
          </Form.Item>
        </>
      )}

      {taskType === "daily" && (
        <Form.Item
          name="timer_preset"
          label="计时预设（可选，单位秒）"
          tooltip="设置倒计时时长，如 1500=25分钟。留空则为正向计时"
        >
          <InputNumber
            style={{ width: 200 }}
            min={60}
            max={7200}
            step={300}
            placeholder="留空使用正计时"
            addonAfter="秒"
          />
        </Form.Item>
      )}

      <Form.Item name="tag" label="标签">
        <Input style={{ width: 200 }} placeholder="如：学习、工作" maxLength={50} />
      </Form.Item>

      <Form.Item style={{ marginTop: 8 }}>
        <Space>
          <Button type="primary" htmlType="submit" loading={loading} style={{ borderRadius: 10 }}>
            {initialValues ? "保存修改" : "创建任务"}
          </Button>
          <Button onClick={onCancel} style={{ borderRadius: 10 }}>取消</Button>
        </Space>
      </Form.Item>
    </Form>
  );
}
