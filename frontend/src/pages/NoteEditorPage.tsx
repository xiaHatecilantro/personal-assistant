import {
  ArrowLeftOutlined,
  SaveOutlined,
  EditOutlined,
  EyeOutlined,
} from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { App, Button, Spin, Typography } from "antd";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { motion } from "motion/react";
import { createNote, fetchNote, fetchNotes, updateNote } from "../api/notes";

/* ── Markdown → HTML ── */

function escapeHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function renderMarkdown(md: string): string {
  const blocks: string[] = [];
  let html = md;
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_m, _lang, code) => {
    blocks.push(`<pre><code>${escapeHtml(code.trim())}</code></pre>`);
    return `%%B${blocks.length - 1}%%`;
  });
  html = html.replace(/`([^`]+)`/g, (_m, c) => `<code>${escapeHtml(c)}</code>`);
  html = html.replace(/^#### (.+)$/gm, "<h4>$1</h4>");
  html = html.replace(/^### (.+)$/gm, "<h3>$1</h3>");
  html = html.replace(/^## (.+)$/gm, "<h2>$1</h2>");
  html = html.replace(/^# (.+)$/gm, "<h1>$1</h1>");
  html = html.replace(/\*\*\*(.+?)\*\*\*/g, "<strong><em>$1</em></strong>");
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");
  html = html.replace(/~~(.+?)~~/g, "<del>$1</del>");
  html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1">');
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>');
  html = html.replace(/\[\[([^\]]+)\]\]/g, '<span style="color:#1677ff;background:#e6f4ff;padding:0 4px;border-radius:4px">$1</span>');
  html = html.replace(/^\- (.+)$/gm, "<li>$1</li>");
  html = html.replace(/^(\d+)\. (.+)$/gm, "<li>$2</li>");
  html = html.replace(/^---$/gm, "<hr>");
  html = html.replace(/\n\n+/g, "</p><p>");
  html = "<p>" + html + "</p>";
  html = html.replace(/%%B(\d+)%%/g, (_m, i) => blocks[Number(i)] || "");
  html = html.replace(/<p>\s*<\/p>/g, "");
  ["ul", "ol", "h1", "h2", "h3", "h4", "pre", "blockquote", "hr"].forEach((tag) => {
    html = html.replace(new RegExp(`<p>(<${tag}[^>]*>)`, "g"), "$1");
    html = html.replace(new RegExp(`(<\/${tag}>)<\/p>`, "g"), "$1");
  });
  return html;
}

function countStats(text: string) {
  return { chars: text.length, words: text.trim().split(/\s+/).filter(Boolean).length, lines: text.split("\n").length };
}

/* ═══════════════════════════════════════════ */

export default function NoteEditorPage() {
  const raw = useParams();
  const id = raw.id;
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { message } = App.useApp();
  const isNew = !id || id === "new";

  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [saving, setSaving] = useState(false);
  const [showPreview, setShowPreview] = useState(true);
  const [lastSaved, setLastSaved] = useState("");

  const { data: note, isLoading, isError } = useQuery({
    queryKey: ["notes", Number(id)],
    queryFn: () => fetchNote(Number(id)),
    enabled: !!id && !isNew,
  });

  const { data: allNotes } = useQuery({
    queryKey: ["notes"],
    queryFn: () => fetchNotes({}),
  });

  // 加载已有笔记
  useEffect(() => {
    if (note) {
      setTitle(note.title || "");
      setContent(note.content || "");
    }
  }, [note]);

  // 新建笔记预填
  useEffect(() => {
    if (isNew) {
      const t = searchParams.get("title") || "";
      const c = searchParams.get("content") || "";
      if (t) setTitle(t);
      if (c) setContent(c);
    }
  }, [isNew, searchParams]);

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (isNew) {
        const res = await createNote({
          title: title || "未命名笔记", content, category: null,
          tags: [], source_url: null, is_pinned: false,
        });
        return res;
      }
      return updateNote(Number(id), {
        title: title || "未命名笔记", content,
        category: note?.category || null, tags: note?.tags || [],
        source_url: note?.source_url || null, is_pinned: note?.is_pinned || false,
      });
    },
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ["notes"] });
      message.success("已保存");
      setLastSaved(new Date().toLocaleTimeString("zh-CN"));
      if (isNew && (res as unknown as { id: number }).id) {
        navigate(`/notes/${(res as unknown as { id: number }).id}/edit`, { replace: true });
      }
    },
    onError: () => message.error("保存失败"),
  });

  // Ctrl+S
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault();
        setSaving(true);
        saveMutation.mutate(undefined as never, { onSettled: () => setSaving(false) });
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [saveMutation]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === "Tab") {
      e.preventDefault();
      const ta = e.currentTarget;
      const s = ta.selectionStart;
      setContent(content.slice(0, s) + "  " + content.slice(ta.selectionEnd));
      setTimeout(() => { ta.selectionStart = ta.selectionEnd = s + 2; }, 0);
    }
  }, [content]);

  const stats = useMemo(() => countStats(content), [content]);
  const previewHtml = useMemo(() => renderMarkdown(content), [content]);

  const notesByCategory = useMemo(() => {
    const map: Record<string, typeof allNotes> = {};
    for (const n of allNotes || []) {
      const cat = n.category || "未分类";
      if (!map[cat]) map[cat] = [];
      map[cat]!.push(n);
    }
    return map;
  }, [allNotes]);

  // 加载中
  if (isLoading) {
    return <Spin style={{ display: "block", textAlign: "center", marginTop: 80 }} />;
  }

  // 加载失败
  if (isError || (!isLoading && !isNew && !note)) {
    return (
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 16 }}>
        <Typography.Text type="secondary">笔记加载失败，可能已被删除</Typography.Text>
        <Button onClick={() => navigate("/notes")}>返回列表</Button>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
      {/* ── 左侧目录 ── */}
      <div style={{
        width: 160, flexShrink: 0, overflow: "auto",
        background: "#fafafa", borderRight: "1px solid #f0f0f0", padding: "10px 0",
      }}>
        <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate("/notes")}
          style={{ margin: "0 6px 10px", color: "#999", fontSize: 12 }}>
          返回
        </Button>
        {allNotes && allNotes.length > 0 ? (
          Object.entries(notesByCategory).map(([cat, notes]) => (
            <div key={cat} style={{ marginBottom: 6 }}>
              <div style={{
                fontSize: 10, fontWeight: 600, color: "#bbb", padding: "3px 14px",
                textTransform: "uppercase", letterSpacing: "0.05em",
              }}>
                {cat}
              </div>
              {notes!.map((n) => (
                <div key={n.id} onClick={() => navigate(`/notes/${n.id}/edit`)} style={{
                  padding: "5px 14px", fontSize: 12, cursor: "pointer",
                  color: n.id === Number(id) ? "#1677ff" : "#555",
                  background: n.id === Number(id) ? "#e6f4ff" : "transparent",
                  fontWeight: n.id === Number(id) ? 600 : 400,
                  overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                  borderRadius: "0 16px 16px 0", marginRight: 6,
                }}>
                  {n.title}
                </div>
              ))}
            </div>
          ))
        ) : null}
      </div>

      {/* ── 编辑器主体 ── */}
      <motion.div
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.15 }}
        style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}
      >
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="笔记标题..."
          style={{
            width: "100%", border: "none", outline: "none",
            fontSize: 20, fontWeight: 700, color: "#1a1a1a",
            background: "transparent", padding: "14px 20px 8px",
            fontFamily: "inherit", flexShrink: 0,
          }}
        />

        <div style={{ flex: 1, display: "flex", minHeight: 0 }}>
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="开始写作... Markdown 语法。[[页面名称]] 创建关联。"
            style={{
              flex: 1, border: "none", borderTop: "1px solid #f0f0f0",
              outline: "none", resize: "none",
              fontSize: 15, lineHeight: 1.8,
              fontFamily: "'JetBrains Mono', Consolas, Monaco, monospace",
              padding: "20px 20px 40px", background: "transparent", color: "#333",
            }}
          />
          {showPreview && (
            <div
              className="markdown-preview"
              dangerouslySetInnerHTML={{ __html: previewHtml }}
              style={{
                flex: 1, overflow: "auto",
                padding: "20px 20px 40px",
                borderLeft: "1px solid #f0f0f0", borderTop: "1px solid #f0f0f0",
                fontSize: 15, lineHeight: 1.8, color: "#333",
              }}
            />
          )}
        </div>

        <div style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "6px 20px", borderTop: "1px solid #f0f0f0",
          fontSize: 11, color: "#bbb", flexShrink: 0,
        }}>
          <div style={{ display: "flex", gap: 14 }}>
            <span>{stats.chars} 字符</span>
            <span>{stats.words} 词</span>
            <span>{stats.lines} 行</span>
            {lastSaved && <span style={{ color: "#52c41a" }}>已保存 {lastSaved}</span>}
          </div>
          <div style={{ display: "flex", gap: 6 }}>
            <Button type="text" size="small"
              icon={showPreview ? <EyeOutlined /> : <EditOutlined />}
              onClick={() => setShowPreview(!showPreview)}
              style={{ color: "#999", fontSize: 11 }}>
              {showPreview ? "隐藏" : "预览"}
            </Button>
            <Button type="primary" size="small" icon={<SaveOutlined />}
              onClick={() => { setSaving(true); saveMutation.mutate(undefined as never, { onSettled: () => setSaving(false) }); }}
              loading={saving} style={{ borderRadius: 6 }}>
              保存
            </Button>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
