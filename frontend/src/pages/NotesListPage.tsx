import {
  DeleteOutlined,
  EditOutlined,
  ImportOutlined,
  LinkOutlined,
  PlusOutlined,
  SearchOutlined,
  PushpinFilled,
} from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { App, Button, Input, message as antMsg, Popconfirm, Select, Spin } from "antd";
import { useRef } from "react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "motion/react";
import { deleteNote, fetchNotes, importFile } from "../api/notes";
import type { Note } from "../types/note";
import EmptyState from "../components/ui/EmptyState";

function NoteCard({ note, delay }: { note: Note; delay: number }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { message } = App.useApp();

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteNote(id),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["notes"] }); message.success("已删除"); },
  });

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay, ease: [0.25, 1, 0.5, 1] }}
      onClick={() => navigate(`/notes/${note.id}`)}
      style={{
        background: "#fefdfb", borderRadius: 16, border: "1px solid #f0ede5",
        padding: "22px 24px", cursor: "pointer",
        transition: "box-shadow 0.15s",
        display: "flex", flexDirection: "column", gap: 12,
      }}
      onMouseEnter={(e) => { (e.currentTarget as HTMLDivElement).style.boxShadow = "0 4px 20px rgba(0,0,0,0.06)"; }}
      onMouseLeave={(e) => { (e.currentTarget as HTMLDivElement).style.boxShadow = "none"; }}
    >
      {/* 标题行 */}
      <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
        {note.is_pinned && <PushpinFilled style={{ color: "#fa8c16", fontSize: 14, marginTop: 2 }} />}
        <span style={{ flex: 1, fontSize: 16, fontWeight: 600, color: "#1a1a1a", lineHeight: 1.4 }}>
          {note.title}
        </span>
      </div>

      {/* 摘要 */}
      {note.content && (
        <div style={{ fontSize: 13, color: "#999", lineHeight: 1.6, overflow: "hidden", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical" }}>
          {note.content.slice(0, 120)}
        </div>
      )}

      {/* 标签 + 元信息 */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        {note.category && (
          <span style={{ fontSize: 11, padding: "2px 10px", borderRadius: 8, background: "#e6f4ff", color: "#1677ff", fontWeight: 500 }}>
            {note.category}
          </span>
        )}
        {note.domain && (
          <span style={{ fontSize: 11, padding: "2px 10px", borderRadius: 8, background: "#f0fdf4", color: "#52c41a", fontWeight: 500 }}>
            {note.domain}
          </span>
        )}
        {note.tags?.map((t: string) => (
          <span key={t} style={{ fontSize: 11, color: "#bbb" }}>#{t}</span>
        ))}
        <div style={{ flex: 1 }} />
        {note.wikilinks?.length > 0 && (
          <span style={{ fontSize: 11, color: "#bbb" }}>
            <LinkOutlined /> {note.wikilinks.length}
          </span>
        )}
        <span style={{ fontSize: 11, color: "#ccc" }}>{note.updated_at?.slice(0, 10)}</span>
      </div>

      {/* 操作 */}
      <div style={{ display: "flex", gap: 4 }} onClick={(e) => e.stopPropagation()}>
        <Button type="text" size="small" icon={<EditOutlined />}
          onClick={(e) => { e.stopPropagation(); navigate(`/notes/${note.id}`); }}>编辑</Button>
        <Popconfirm
          title="确定删除？" okText="删除" cancelText="取消" okButtonProps={{ danger: true }}
          onConfirm={(e) => { e?.stopPropagation(); deleteMutation.mutate(note.id); }}
          onCancel={(e) => e?.stopPropagation()}
        >
          <Button type="text" danger size="small" icon={<DeleteOutlined />}>删除</Button>
        </Popconfirm>
      </div>
    </motion.div>
  );
}

export default function NotesListPage() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState<string | null>(null);
  const [domain, setDomain] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [importing, setImporting] = useState(false);

  const { data: notes, isLoading } = useQuery({
    queryKey: ["notes", { search, category, domain }],
    queryFn: () => fetchNotes({ search: search || undefined, category: category || undefined, domain: domain || undefined }),
  });

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    try {
      const res = await importFile(file);
      antMsg.success("导入成功，正在跳转编辑器...");
      navigate(`/notes/new/edit?title=${encodeURIComponent(res.title)}&content=${encodeURIComponent(res.content)}`);
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      antMsg.error(detail || "导入失败");
    } finally {
      setImporting(false);
      e.target.value = "";
    }
  };

  return (
    <div style={{ maxWidth: 960, margin: "0 auto", paddingTop: 8, height: "100%", overflow: "auto" }}>
      {/* 顶部 */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <div style={{ display: "flex", gap: 12, flex: 1 }}>
          <Input
            placeholder="搜索笔记..."
            prefix={<SearchOutlined />}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            allowClear
            style={{ maxWidth: 260, borderRadius: 10 }}
          />
          <Select allowClear placeholder="分类" style={{ width: 120, borderRadius: 10 }}
            value={category} onChange={(v) => setCategory(v || null)}
            options={[
              { value: "编程", label: "编程" }, { value: "学习", label: "学习" },
              { value: "生活", label: "生活" }, { value: "工作", label: "工作" },
            ]}
          />
          <Select allowClear placeholder="领域" style={{ width: 120 }}
            value={domain} onChange={(v) => setDomain(v || null)}
            options={[
              { value: "Python", label: "Python" }, { value: "AI", label: "AI" },
              { value: "前端", label: "前端" }, { value: "后端", label: "后端" },
            ]}
          />
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <input
            ref={fileInputRef}
            type="file"
            accept=".md,.txt,.docx,.pptx,.pdf,.html,.htm"
            style={{ display: "none" }}
            onChange={handleImport}
          />
          <Button
            icon={<ImportOutlined />}
            onClick={() => fileInputRef.current?.click()}
            loading={importing}
            style={{ borderRadius: 10 }}
          >
            导入
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate("/notes/new")} style={{ borderRadius: 10 }}>
            新建笔记
          </Button>
        </div>
      </div>

      <Spin spinning={isLoading}>
        {notes && notes.length > 0 ? (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))", gap: 14 }}>
            {notes.map((n, i) => (
              <NoteCard key={n.id} note={n} delay={i * 0.04} />
            ))}
          </div>
        ) : (
          <EmptyState icon="📝" title="还没有笔记" hint="点击上方按钮创建第一篇笔记" />
        )}
      </Spin>
    </div>
  );
}
