import { createPortal } from "react-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { App, Button, Form, Input, Select, Switch } from "antd";
import { useNavigate, useSearchParams } from "react-router-dom";
import { motion } from "motion/react";
import { createNote } from "../api/notes";

interface QuickMeta {
  title: string;
  category: string | null;
  tags: string[];
  is_pinned: boolean;
}

export default function NoteCreatePage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const queryClient = useQueryClient();
  const { message } = App.useApp();
  const [form] = Form.useForm<QuickMeta>();

  const defaultTitle = params.get("title") || "";
  const defaultContent = params.get("content") || "";

  const mutation = useMutation({
    mutationFn: (values: QuickMeta) =>
      createNote({ ...values, content: defaultContent || "", source_url: null }),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ["notes"] });
      message.success("已创建，进入编辑器");
      navigate(`/notes/${res.id}/edit`);
    },
  });

  return createPortal(
    <div
      onClick={() => navigate(-1)}
      style={{
        position: "fixed", inset: 0, zIndex: 1000,
        display: "flex", alignItems: "center", justifyContent: "center",
        background: "rgba(0,0,0,0.25)", backdropFilter: "blur(4px)",
      }}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.94, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.94, y: 20 }}
        transition={{ duration: 0.25, ease: [0.25, 1, 0.5, 1] }}
        onClick={(e) => e.stopPropagation()}
        style={{
          width: 440, background: "#fff", borderRadius: 20,
          padding: "32px 32px 20px",
          boxShadow: "0 20px 60px rgba(0,0,0,0.15)",
        }}
      >
        <h2 style={{ fontSize: 20, fontWeight: 700, color: "#1a1a1a", margin: "0 0 24px" }}>
          新建笔记
        </h2>

        <Form
          form={form}
          layout="vertical"
          onFinish={(values) => mutation.mutate(values)}
          initialValues={{
            title: defaultTitle,
            category: null,
            tags: [],
            is_pinned: false,
          }}
        >
          <Form.Item
            name="title"
            label="标题"
            rules={[{ required: true, message: "请输入笔记标题" }, { max: 200 }]}
          >
            <Input placeholder="起个名字..." style={{ borderRadius: 8 }} autoFocus />
          </Form.Item>

          <div style={{ display: "flex", gap: 16 }}>
            <Form.Item name="category" label="分类" style={{ flex: 1 }}>
              <Select allowClear placeholder="选择分类" style={{ width: "100%" }}
                options={[
                  { value: "编程", label: "编程" }, { value: "学习", label: "学习" },
                  { value: "生活", label: "生活" }, { value: "工作", label: "工作" },
                ]}
              />
            </Form.Item>
            <Form.Item name="is_pinned" label="置顶" valuePropName="checked"
              style={{ minWidth: 60 }}>
              <Switch />
            </Form.Item>
          </div>

          <Form.Item name="tags" label="标签">
            <Select mode="tags" placeholder="输入标签后回车" style={{ width: "100%" }} />
          </Form.Item>

          <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 24 }}>
            <Button onClick={() => navigate(-1)} style={{ borderRadius: 8 }}>取消</Button>
            <Button type="primary" htmlType="submit" loading={mutation.isPending}
              style={{ borderRadius: 8 }}>
              创建并编辑
            </Button>
          </div>
        </Form>
      </motion.div>
    </div>,
    document.body,
  );
}
