import { Button, Form, Input, Select, Space, Switch } from "antd";
import { useEffect } from "react";

export interface NoteFormValues {
  title: string;
  content: string;
  category: string | null;
  domain: string | null;
  tags: string[];
  source_url: string | null;
  is_pinned: boolean;
}

interface Props {
  initialValues?: Partial<NoteFormValues>;
  onSubmit: (values: NoteFormValues) => void;
  onCancel: () => void;
  loading?: boolean;
}

export default function NoteForm({ initialValues, onSubmit, onCancel, loading }: Props) {
  const [form] = Form.useForm<NoteFormValues>();

  useEffect(() => {
    if (initialValues) {
      form.setFieldsValue({
        title: initialValues.title || "",
        content: initialValues.content || "",
        category: initialValues.category || null,
        domain: initialValues.domain || null,
        tags: initialValues.tags || [],
        source_url: initialValues.source_url || null,
        is_pinned: initialValues.is_pinned || false,
      });
    }
  }, [initialValues, form]);

  return (
    <Form
      form={form}
      layout="vertical"
      onFinish={(values) =>
        onSubmit({
          ...values,
          tags: Array.isArray(values.tags)
            ? values.tags.filter((t: string) => t.trim())
            : [],
        })
      }
      initialValues={{
        category: null,
        domain: null,
        tags: [],
        is_pinned: false,
        content: "",
      }}
      style={{ maxWidth: 720, background: "#fff", borderRadius: 20, border: "1px solid #f0f0f0", padding: "28px 28px 12px" }}
    >
      <Form.Item
        name="title"
        label="标题"
        rules={[{ required: true, message: "请输入笔记标题" }, { max: 200 }]}
      >
        <Input placeholder="笔记标题" />
      </Form.Item>

      <Form.Item name="content" label="内容（Markdown）">
        <Input.TextArea
          rows={14}
          placeholder='支持 Markdown 语法。使用 [[页面名称]] 创建关联。'
          style={{ fontFamily: "Consolas, Monaco, monospace", fontSize: 13 }}
        />
      </Form.Item>

      <Space size="middle" align="start">
        <Form.Item name="category" label="分类">
          <Select
            allowClear
            placeholder="选择分类"
            style={{ width: 160 }}
            options={[
              { value: "编程", label: "编程" },
              { value: "学习", label: "学习" },
              { value: "生活", label: "生活" },
              { value: "工作", label: "工作" },
            ]}
          />
        </Form.Item>

        <Form.Item name="domain" label="领域">
          <Select
            allowClear
            placeholder="选择领域"
            style={{ width: 160 }}
            options={[
              { value: "Python", label: "Python" },
              { value: "AI", label: "AI" },
              { value: "前端", label: "前端" },
              { value: "后端", label: "后端" },
            ]}
          />
        </Form.Item>

        <Form.Item name="is_pinned" label="置顶" valuePropName="checked">
          <Switch />
        </Form.Item>
      </Space>

      <Space size="middle">
        <Form.Item name="tags" label="标签" help="用英文逗号分隔，如 python,基础">
          <Select
            mode="tags"
            placeholder="输入标签后回车"
            style={{ width: 280 }}
          />
        </Form.Item>

        <Form.Item name="source_url" label="来源 URL">
          <Input placeholder="原始材料链接" style={{ width: 280 }} />
        </Form.Item>
      </Space>

      <Form.Item style={{ marginTop: 16 }}>
        <Space>
          <Button type="primary" htmlType="submit" loading={loading} style={{ borderRadius: 10 }}>
            {initialValues?.title ? "保存修改" : "创建笔记"}
          </Button>
          <Button onClick={onCancel} style={{ borderRadius: 10 }}>取消</Button>
        </Space>
      </Form.Item>
    </Form>
  );
}
