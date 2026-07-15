import { DeleteOutlined, PlusOutlined } from "@ant-design/icons";
import {
  Button,
  Drawer,
  Form,
  Input,
  Select,
  Space,
  Table,
  Typography,
} from "antd";
import { useState } from "react";
import { useModelStore } from "../store/modelStore";

interface Props {
  open: boolean;
  onClose: () => void;
}

export default function ModelSettings({ open, onClose }: Props) {
  const { models, addModel, removeModel, activeModelId, setActive } =
    useModelStore();
  const [adding, setAdding] = useState(false);
  const [form] = Form.useForm();

  const active = models.find((m) => m.id === activeModelId);

  const handleAdd = () => {
    form.validateFields().then((values) => {
      const id = Date.now().toString();
      addModel({ id, ...values });
      form.resetFields();
      setAdding(false);
    });
  };

  return (
    <Drawer
      title="模型设置"
      open={open}
      onClose={onClose}
      size="large"
      styles={{ body: { paddingBottom: 40 } }}
    >
      <Typography.Title level={5} style={{ marginTop: 0 }}>
        当前模型
      </Typography.Title>
      {active ? (
        <div
          style={{
            padding: "12px 16px",
            background: "#e6f4ff",
            borderRadius: 8,
            marginBottom: 24,
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <div>
            <Typography.Text strong style={{ fontSize: 15 }}>
              {active.name}
            </Typography.Text>
            <Typography.Text type="secondary" style={{ display: "block", fontSize: 12 }}>
              {active.provider} · {active.model}
            </Typography.Text>
          </div>
          <Button size="small" type="primary" ghost disabled>
            已激活
          </Button>
        </div>
      ) : (
        <Typography.Text type="secondary" style={{ display: "block", marginBottom: 24 }}>
          请选择一个模型
        </Typography.Text>
      )}

      <Typography.Title level={5}>已配置模型</Typography.Title>

      <Table
        dataSource={models}
        rowKey="id"
        pagination={false}
        size="small"
        columns={[
          {
            title: "名称",
            dataIndex: "name",
            render: (name: string, r) => (
              <div>
                <div style={{ fontWeight: r.id === activeModelId ? 600 : 400 }}>{name}</div>
                <Typography.Text type="secondary" style={{ fontSize: 11 }}>
                  {r.provider} · {r.model}
                </Typography.Text>
              </div>
            ),
          },
          {
            title: "",
            width: 160,
            render: (_, r) => (
              <Space>
                {r.id !== activeModelId ? (
                  <Button size="small" type="link" onClick={() => setActive(r.id)}>
                    激活
                  </Button>
                ) : (
                  <Button size="small" type="link" disabled>
                    当前
                  </Button>
                )}
                <Button
                  size="small"
                  type="link"
                  danger
                  icon={<DeleteOutlined />}
                  onClick={() => removeModel(r.id)}
                  disabled={models.length <= 1}
                />
              </Space>
            ),
          },
        ]}
      />

      {adding && (
        <div
          style={{
            marginTop: 16,
            padding: 16,
            background: "#fafafa",
            borderRadius: 8,
          }}
        >
          <Form form={form} layout="vertical" initialValues={{ provider: "custom" }}>
            <Form.Item name="name" label="名称" rules={[{ required: true }]}>
              <Input placeholder="如：我的 DeepSeek" />
            </Form.Item>
            <Form.Item name="provider" label="提供商">
              <Select
                options={[
                  { value: "deepseek", label: "DeepSeek" },
                  { value: "openai", label: "OpenAI" },
                  { value: "ollama", label: "Ollama" },
                  { value: "custom", label: "自定义" },
                ]}
              />
            </Form.Item>
            <Form.Item name="baseUrl" label="API 地址" rules={[{ required: true }]}>
              <Input placeholder="https://api.deepseek.com/v1" />
            </Form.Item>
            <Form.Item name="model" label="模型名" rules={[{ required: true }]}>
              <Input placeholder="deepseek-chat" />
            </Form.Item>
            <Form.Item name="apiKey" label="API Key">
              <Input.Password placeholder="sk-..." />
            </Form.Item>
            <Space>
              <Button type="primary" onClick={handleAdd}>
                添加
              </Button>
              <Button onClick={() => { setAdding(false); form.resetFields(); }}>
                取消
              </Button>
            </Space>
          </Form>
        </div>
      )}

      {!adding && (
        <Button
          type="dashed"
          block
          icon={<PlusOutlined />}
          onClick={() => setAdding(true)}
          style={{ marginTop: 16 }}
        >
          添加模型
        </Button>
      )}
    </Drawer>
  );
}
