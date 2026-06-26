import {
  ArrowLeftOutlined,
  SaveOutlined,
  EditOutlined,
  EyeOutlined,
} from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { App, Button, Spin } from "antd";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { motion } from "motion/react";
import { createNote, fetchNote, fetchNotes, updateNote } from "../api/notes";
import EmptyState from "../components/ui/EmptyState";

/* ── 简易 Markdown → HTML 渲染 ── */

function renderMarkdown(md: string): string {
  let html = md;
  // 逃逸 HTML 特殊字符（先处理，防止注入）
  // 代码块：提取出来保护
  const codeBlocks: string[] = [];
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_m, lang, code) => {
    codeBlocks.push(`<pre><code>${escapeHtml(code.trim())}</code></pre>`);
    return `%%CODEBLOCK_${codeBlocks.length - 1}%%`;
  });
  // 行内代码
  html = html.replace(/`([^`]+)`/g, (_m, code) => `<code>${escapeHtml(code)}</code>`);
  // 标题
  html = html.replace(/^#### (.+)$/gm, "<h4>$1</h4>");
  html = html.replace(/^### (.+)$/gm, "<h3>$1</h3>");
  html = html.replace(/^## (.+)$/gm, "<h2>$1</h2>");
  html = html.replace(/^# (.+)$/gm, "<h1>$1</h1>");
  // 粗体/斜体
  html = html.replace(/\*\*\*(.+?)\*\*\*/g, "<strong><em>$1</em></strong>");
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");
  // 删除线
  html = html.replace(/~~(.+?)~~/g, "<del>$1</del>");
  // 图片 / 链接
  html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1">');
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>');
  // Wikilinks
  html = html.replace(/\[\[([^\]]+)\]\]/g, '<span class="wikilink" style="color:#1677ff;background:#e6f4ff;padding:0 4px;border-radius:4px;cursor:pointer;">$1</span>');
  // 列表
  html = html.replace(/^\- (.+)$/gm, "<li>$1</li>");
  html = html.replace(/^(\d+)\. (.+)$/gm, "<li>$2</li>");
  // 分隔线
  html = html.replace(/^---$/gm, "<hr>");
  // 段落
  html = html.replace(/\n\n+/g, "</p><p>");
  html = "<p>" + html + "</p>";
  // 还原代码块
  html = html.replace(/%%CODEBLOCK_(\d+)%%/g, (_m, i) => codeBlocks[Number(i)] || "");
  // 清理
  html = html.replace(/<p>\s*<\/p>/g, "");
  html = html.replace(/<p>(<ul>)/g, "$1");
  html = html.replace(/(<\/ul>)<\/p>/g, "$1");
  html = html.replace(/<p>(<h[1-4]>)/g, "$1");
  html = html.replace(/(<\/h[1-4]>)<\/p>/g, "$1");
  html = html.replace(/<p>(<pre>)/g, "$1");
  html = html.replace(/(<\/pre>)<\/p>/g, "$1");
  return html;
}

function escapeHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/* ── 字数/行数 ── */

function countStats(text: string) {
  return {
    chars: text.length,
    words: text.trim() ? text.trim().split(/\s+/).length : 0,
    lines: text.split("\n").length,
  };
}

/* ═══════════════════════════════════════════ */

export default function NoteEditorPage() {
  const rawParams = useParams();
  const id = rawParams.id;
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { message } = App.useApp();
  const isNew = !id || id === "new";

  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [saving, setSaving] = useState(false);
  const [showPreview, setShowPreview] = useState(true);
  const [lastSaved, setLastSaved] = useState<string | null,>(null);
  const editorRef = useRef<HTMLTextAreaElement | null,>(null);
  const previewRef = useRef<HTMLDivElement | null,>(null);

  const { data: note, isLoading } = useQuery({
    queryKey: ["notes", Number(id)],
    queryFn: () => fetchNote(Number(id)),
    enabled: !!id && !isNew,
  });

  const { data: allNotes } = useQuery({
    queryKey: ["notes"],
    queryFn: () => fetchNotes({}),
  });

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (isNew) {
        const res = await createNote({ title: title || "未命名笔记", content, category: null, tags: [], source_url: null, domain: null, is_pinned: false });
        return res;
      }
      return updateNote(Number(id), { title: title || "未命名笔记", content, category: note?.category || null, tags: note?.tags || [], source_url: note?.source_url || null, domain: note?.domain || null, is_pinned: note?.is_pinned || false });
    },
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ["notes"] });
      message.success("已保存");
      setLastSaved(new Date().toLocaleTimeString("zh-CN"));
      if (isNew && (res as { id: number }).id) {
        navigate(`/notes/${(res as { id: number }).id}/edit`, { replace: true });
      }
    },
    onError: () => message.error("保存失败"),
  });

  // 加载已有笔记
  useEffect(() => {
    if (note) {
      setTitle(note.title);
      setContent(note.content || "");
    }
  }, [note]);

  // 新建笔记预填（从 URL 参数）
  useEffect(() => {
    if (isNew) {
      const t = searchParams.get("title");
      const c = searchParams.get("content");
      if (t) setTitle(t);
      if (c) setContent(c);
    }
  }, [isNew, searchParams]);

  // Ctrl+S 保存
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault();
        setSaving(true);
        saveMutation.mutate(undefined, { onSettled: () => setSaving(false) });
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [saveMutation]);

  // 编辑器 Tab 键插入空格
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === "Tab") {
      e.preventDefault();
      const ta = e.currentTarget as HTMLTextAreaElement;
      const start = ta.selectionStart;
      const end = ta.selectionEnd;
      const newVal = content.slice(0, start) + "  " + content.slice(end);
      setContent(newVal);
      setTimeout(() => { ta.selectionStart = ta.selectionEnd = start + 2; }, 0);
    }
  }, [content]);

  // 同步滚动
  const handleEditorScroll = useCallback(() => {
    const editor = editorRef.current;
    const preview = previewRef.current;
    if (!editor || !preview) return;
    const ratio = editor.scrollTop / (editor.scrollHeight - editor.clientHeight);
    preview.scrollTop = ratio * (preview.scrollHeight - preview.clientHeight);
  }, []);

  const stats = useMemo(() => countStats(content), [content]);

  // 按分类分组的笔记（用于左侧目录）
  const notesByCategory = useMemo(() => {
    const map: Record<string, typeof allNotes> = {};
    for (const n of allNotes || []) {
      const cat = n.category || "未分类";
      if (!map[cat]) map[cat] = [];
      map[cat].push(n);
    }
    return map;
  }, [allNotes]);

  const previewHtml = useMemo(() => renderMarkdown(content), [content]);

  if (isLoading) return <Spin style={{ display: "block", textAlign: "center", marginTop: 80 }} />;

  return (
    <div style={{ display: "flex", height: "100%", gap: 0 }}>
      {/* ── 左侧：笔记目录 ── */}
      <div style={{
        width: 200, flexShrink: 0, overflow: "auto",
        background: "#fafafa", borderRight: "1px solid #f0f0f0",
        padding: "12px 0",
      }}>
        <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate("/notes")}
          style={{ margin: "0 8px 12px", color: "#999", fontSize: 13 }}>
          返回列表
        </Button>
        {allNotes && allNotes.length > 0 ? (
          Object.entries(notesByCategory).map(([cat, notes]) => (
            <div key={cat} style={{ marginBottom: 8 }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: "#bbb", padding: "4px 16px", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                {cat}
              </div>
              {notes!.map((n) => (
                <div
                  key={n.id}
                  onClick={() => navigate(`/notes/${n.id}/edit`)}
                  style={{
                    padding: "6px 16px", fontSize: 13, cursor: "pointer",
                    color: n.id === Number(id) ? "#1677ff" : "#555",
                    background: n.id === Number(id) ? "#e6f4ff" : "transparent",
                    fontWeight: n.id === Number(id) ? 600 : 400,
                    overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                    transition: "background 0.1s",
                    borderRadius: "0 20px 20px 0", marginRight: 8,
                  }}
                  onMouseEnter={(e) => { if (n.id !== Number(id)) (e.currentTarget as HTMLDivElement).style.background = "#f0f0f0"; }}
                  onMouseLeave={(e) => { if (n.id !== Number(id)) (e.currentTarget as HTMLDivElement).style.background = "transparent"; }}
                >
                  {n.title}
                </div>
              ))}
            </div>
          ))
        ) : (
          <EmptyState icon="📂" title="暂无笔记" />
        )}
      </div>

      {/* ── 中间：编辑器 ── */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.2 }}
        style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}
      >
        {/* 标题 */}
        <div style={{ padding: "16px 24px 0", flexShrink: 0 }}>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="笔记标题..."
            style={{
              width: "100%", border: "none", outline: "none",
              fontSize: 22, fontWeight: 700, color: "#1a1a1a",
              background: "transparent", padding: "4px 0",
              fontFamily: "inherit",
            }}
          />
        </div>

        {/* 编辑区 */}
        <div style={{
          flex: 1, display: "flex", minHeight: 0, borderTop: "1px solid #f0f0f0",
          margin: "12px 24px 0",
        }}>
          <textarea
            ref={editorRef}
            value={content}
            onChange={(e) => setContent(e.target.value)}
            onKeyDown={handleKeyDown}
            onScroll={handleEditorScroll}
            placeholder="开始写作... 支持 Markdown 语法。使用 [[页面名称]] 创建关联。"
            style={{
              flex: 1, border: "none", outline: "none", resize: "none",
              fontSize: 15, lineHeight: 1.75, fontFamily: "'JetBrains Mono', Consolas, Monaco, monospace",
              padding: "16px 24px 16px 0",
              background: "transparent", color: "#333",
            }}
          />
          {showPreview && (
            <div
              ref={previewRef}
              className="markdown-preview"
              dangerouslySetInnerHTML={{ __html: previewHtml }}
              style={{
                flex: 1, overflow: "auto", padding: "16px 0 16px 24px",
                borderLeft: "1px solid #f0f0f0",
                fontSize: 15, lineHeight: 1.75, color: "#333",
              }}
            />
          )}
        </div>

        {/* 底部状态栏 */}
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "8px 24px", borderTop: "1px solid #f0f0f0",
          fontSize: 11, color: "#bbb", flexShrink: 0,
        }}>
          <div style={{ display: "flex", gap: 16 }}>
            <span>{stats.chars} 字符</span>
            <span>{stats.words} 词</span>
            <span>{stats.lines} 行</span>
            {lastSaved && <span>已保存 {lastSaved}</span>}
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <Button type="text" size="small" icon={showPreview ? <EyeOutlined /> : <EditOutlined />}
              onClick={() => setShowPreview(!showPreview)} style={{ color: "#999", fontSize: 11 }}>
              {showPreview ? "隐藏预览" : "显示预览"}
            </Button>
            <Button type="primary" size="small" icon={<SaveOutlined />}
              onClick={() => { setSaving(true); saveMutation.mutate(undefined, { onSettled: () => setSaving(false) }); }}
              loading={saving} style={{ borderRadius: 8 }}>
              保存
            </Button>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
