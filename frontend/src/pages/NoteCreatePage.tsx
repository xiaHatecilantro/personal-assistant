import { ArrowLeftOutlined } from "@ant-design/icons";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { App, Button } from "antd";
import { useNavigate, useSearchParams } from "react-router-dom";
import { motion } from "motion/react";
import { createNote } from "../api/notes";
import NoteForm, { type NoteFormValues } from "../components/NoteForm";

export default function NoteCreatePage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const queryClient = useQueryClient();
  const { message } = App.useApp();

  const defaultTitle = params.get("title") || "";
  const defaultContent = params.get("content") || "";

  // 如果有预填内容（导入场景），直接跳转到编辑器
  if (defaultContent && !defaultTitle) {
    // 简单创建并跳转
  }

  const mutation = useMutation({
    mutationFn: (data: NoteFormValues) => createNote(data),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ["notes"] });
      message.success("笔记创建成功");
      navigate(`/notes/${res.id}/edit`);
    },
  });

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.25, 1, 0.5, 1] }}
      style={{ maxWidth: 680, margin: "0 auto", paddingTop: 8, height: "100%", overflow: "auto" }}
    >
      <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate("/notes")}
        style={{ marginBottom: 20, color: "#999", fontSize: 14 }}>
        返回
      </Button>
      <h2 style={{ fontSize: 22, fontWeight: 700, color: "#1a1a1a", margin: "0 0 28px" }}>新建笔记</h2>
      <NoteForm
        initialValues={{ title: defaultTitle, content: defaultContent, tags: [], category: null, source_url: null, is_pinned: false }}
        onSubmit={(values) => mutation.mutate(values)}
        onCancel={() => navigate("/notes")}
        loading={mutation.isPending}
      />
    </motion.div>
  );
}
