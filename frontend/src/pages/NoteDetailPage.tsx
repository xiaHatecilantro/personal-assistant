import { ArrowLeftOutlined, DeleteOutlined, RobotOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { App, Button, Popconfirm, Spin, Tag, Typography } from "antd";
import { useNavigate, useParams } from "react-router-dom";
import { motion } from "motion/react";
import NoteForm, { type NoteFormValues } from "../components/NoteForm";
import { compileSource, deleteNote, fetchNote, fetchNotes, updateNote } from "../api/notes";

export default function NoteDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { message } = App.useApp();

  const { data: note, isLoading } = useQuery({
    queryKey: ["notes", Number(id)],
    queryFn: () => fetchNote(Number(id)),
    enabled: !!id,
  });

  const { data: allNotes } = useQuery({
    queryKey: ["notes"],
    queryFn: () => fetchNotes(),
    enabled: !!note,
  });

  const updateMutation = useMutation({
    mutationFn: (data: NoteFormValues) => updateNote(Number(id), data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["notes"] }); message.success("笔记已更新"); },
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteNote(Number(id)),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["notes"] }); message.success("笔记已删除"); navigate("/notes"); },
  });

  const compileMutation = useMutation({
    mutationFn: () => compileSource(Number(id)),
    onSuccess: (res) => message.info(res.hint),
  });

  if (isLoading) return <Spin style={{ display: "block", textAlign: "center", marginTop: 80 }} />;
  if (!note) return <div style={{ textAlign: "center", padding: 80, color: "#999" }}>笔记不存在</div>;

  const wikilinks = note.wikilinks || [];
  const linkedNotes = allNotes?.filter((n) => wikilinks.includes(n.title) && n.id !== note.id) || [];
  const brokenLinks = wikilinks.filter((l: string) => !allNotes?.some((n) => n.title === l));

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.25, 1, 0.5, 1] }}
      style={{ maxWidth: 960, margin: "0 auto", paddingTop: 8 }}
    >
      <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate("/notes")}
        style={{ marginBottom: 20, color: "#999", fontSize: 14 }}>
        返回
      </Button>

      <div style={{ display: "flex", gap: 32 }}>
        {/* 主体 */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 28 }}>
            <h2 style={{ fontSize: 22, fontWeight: 700, color: "#1a1a1a", margin: 0 }}>编辑笔记</h2>
            <div style={{ display: "flex", gap: 8 }}>
              {note.source_url && (
                <Button icon={<RobotOutlined />} onClick={() => compileMutation.mutate()} loading={compileMutation.isPending}
                  style={{ borderRadius: 10 }}>LLM 蒸馏</Button>
              )}
              <Popconfirm title="确定删除此笔记？" onConfirm={() => deleteMutation.mutate()}
                okText="删除" cancelText="取消" okButtonProps={{ danger: true }}>
                <Button danger icon={<DeleteOutlined />} loading={deleteMutation.isPending} style={{ borderRadius: 10 }}>删除</Button>
              </Popconfirm>
            </div>
          </div>
          <NoteForm
            initialValues={note}
            onSubmit={(values) => updateMutation.mutate(values)}
            onCancel={() => navigate("/notes")}
            loading={updateMutation.isPending}
          />
        </div>

        {/* 右侧栏：关联页面 */}
        <div style={{ width: 200, flexShrink: 0 }}>
          <div style={{
            background: "#fff", borderRadius: 16, border: "1px solid #f0f0f0",
            padding: 22, position: "sticky", top: 20,
          }}>
            <Typography.Title level={5} style={{ margin: "0 0 12px", fontSize: 15 }}>关联页面</Typography.Title>
            {linkedNotes.length > 0 ? (
              linkedNotes.map((n) => (
                <Tag key={n.id} color="blue" style={{ display: "block", marginBottom: 6, cursor: "pointer", borderRadius: 8 }}
                  onClick={() => navigate(`/notes/${n.id}`)}>{n.title}</Tag>
              ))
            ) : (
              <Typography.Text type="secondary" style={{ fontSize: 13 }}>暂无关联页面</Typography.Text>
            )}
            {brokenLinks.length > 0 && (
              <>
                <Typography.Title level={5} style={{ margin: "20px 0 12px", fontSize: 15 }}>断链</Typography.Title>
                {brokenLinks.map((l: string) => (
                  <Tag key={l} style={{ display: "block", marginBottom: 6, cursor: "pointer", borderRadius: 8 }}
                    onClick={() => navigate(`/notes/new?title=${encodeURIComponent(l)}`)}>{l} +</Tag>
                ))}
              </>
            )}
          </div>
        </div>
      </div>
    </motion.div>
  );
}
