import { ArrowLeftOutlined } from "@ant-design/icons";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { App, Button } from "antd";
import { useNavigate, useSearchParams } from "react-router-dom";
import { createNote } from "../api/notes";
import NoteForm, { type NoteFormValues } from "../components/NoteForm";

export default function NoteCreatePage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const queryClient = useQueryClient();
  const { message } = App.useApp();

  const defaultTitle = params.get("title") || "";

  const mutation = useMutation({
    mutationFn: (data: NoteFormValues) => createNote(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notes"] });
      message.success("笔记创建成功");
      navigate("/notes");
    },
  });

  return (
    <>
      <Button
        type="primary"
        icon={<ArrowLeftOutlined />}
        onClick={() => navigate("/notes")}
        style={{ marginBottom: 24, borderRadius: 6 }}
      >
        返回
      </Button>
      <h2 style={{ marginBottom: 24, fontSize: 18, fontWeight: 600 }}>新建笔记</h2>
      <NoteForm
        initialValues={{ title: defaultTitle, content: "", tags: [], category: null, domain: null, source_url: null, is_pinned: false }}
        onSubmit={(values) => mutation.mutate(values)}
        onCancel={() => navigate("/notes")}
        loading={mutation.isPending}
      />
    </>
  );
}
