import {
  ArrowLeftOutlined,
  SaveOutlined,
  FontColorsOutlined,
  HighlightOutlined,
  ItalicOutlined,
  BoldOutlined,
  LinkOutlined,
  OrderedListOutlined,
  UnorderedListOutlined,
  SettingOutlined,
  PushpinFilled,
  PushpinOutlined,
} from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { App, Button, Input, Popover, Select, Space, Spin, Tooltip, Typography } from "antd";
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
  html = html.replace(/^> (.+)$/gm, "<blockquote>$1</blockquote>");
  html = html.replace(/^- (.+)$/gm, "<li>$1</li>");
  html = html.replace(/^(\d+)\. (.+)$/gm, "<li>$2</li>");
  html = html.replace(/^---$/gm, "<hr>");
  html = html.replace(/\n\n+/g, "</p><p>");
  html = "<p>" + html + "</p>";
  html = html.replace(/%%B(\d+)%%/g, (_m, i) => blocks[Number(i)] || "");
  html = html.replace(/<p>\s*<\/p>/g, "");
  ["ul", "ol", "h1", "h2", "h3", "h4", "pre", "blockquote", "hr"].forEach((tag) => {
    html = html.replace(new RegExp(`<p>(<${tag}[^>]*>)`, "g"), "$1");
    html = html.replace(new RegExp(`(</${tag}>)</p>`, "g"), "$1");
  });
  return html;
}

function countStats(text: string) {
  return { chars: text.length, words: text.trim().split(/\s+/).filter(Boolean).length, lines: text.split("\n").length };
}

const TEXT_COLORS = ["#d4380d", "#d46b08", "#389e0d", "#096dd9", "#722ed1"] as const;
const MARK_COLORS = ["#fff1b8", "#d9f7be", "#bae7ff", "#ffd6e7", "#efdbff"] as const;
const BLOCK_TYPES = [
  { value: "paragraph", label: "正文" },
  { value: "h1", label: "一级标题" },
  { value: "h2", label: "二级标题" },
  { value: "h3", label: "三级标题" },
  { value: "quote", label: "引用" },
  { value: "code", label: "代码块" },
] as const;
type BlockType = (typeof BLOCK_TYPES)[number]["value"];

function normalizeEditorHtml(value: string) {
  if (!value.trim()) return "";
  const hasBlockHtml = /<\/?(p|div|h[1-6]|blockquote|pre|ul|ol|li|br)\b/i.test(value);
  return hasBlockHtml ? value : renderMarkdown(value);
}

function normalizeEditableHtml(html: string, text: string | null) {
  if (!text?.trim() && !/<img\b/i.test(html)) return "";
  return html === "<br>" ? "" : html;
}

function plainTextFromHtml(html: string) {
  return html
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/(p|div|h[1-6]|li|blockquote|pre)>/gi, "\n")
    .replace(/<[^>]+>/g, "")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function detectRichBlockType(range: Range, editor: HTMLElement): BlockType {
  let node: Node | null = range.startContainer;
  if (node.nodeType === Node.TEXT_NODE) node = node.parentElement;

  while (node && node !== editor) {
    if (node instanceof HTMLElement) {
      const tag = node.tagName.toLowerCase();
      if (tag === "h1") return "h1";
      if (tag === "h2") return "h2";
      if (tag === "h3") return "h3";
      if (tag === "blockquote") return "quote";
      if (tag === "pre" || tag === "code") return "code";
    }
    node = node.parentNode;
  }
  return "paragraph";
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
  const [lastSaved, setLastSaved] = useState("");
  const [propsOpen, setPropsOpen] = useState(false);
  const [currentBlockType, setCurrentBlockType] = useState<BlockType>("paragraph");
  const editorRef = useRef<HTMLDivElement | null>(null);
  const selectionRangeRef = useRef<Range | null>(null);
  // 属性 state — 与 title/content 分离
  const [noteCategory, setNoteCategory] = useState<string | null>(null);
  const [noteTags, setNoteTags] = useState<string[]>([]);
  const [notePinned, setNotePinned] = useState(false);
  const [noteSourceUrl, setNoteSourceUrl] = useState("");
  const [noteDomain, setNoteDomain] = useState<string | null>(
    searchParams.get("domain") || null,
  );

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
      const nextContent = normalizeEditorHtml(note.content || "");
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setTitle(note.title || "");
      setContent(nextContent);
      if (editorRef.current) editorRef.current.innerHTML = nextContent;
      setNoteCategory(note.category || null);
      setNoteTags(note.tags || []);
      setNotePinned(!!note.is_pinned);
      setNoteSourceUrl(note.source_url || "");
      setNoteDomain(note.domain || null);
    }
  }, [note]);

  // 新建笔记预填
  useEffect(() => {
    if (isNew) {
      const t = searchParams.get("title") || "";
      const c = searchParams.get("content") || "";
      const d = searchParams.get("domain") || null;
      const nextContent = normalizeEditorHtml(c);
      // eslint-disable-next-line react-hooks/set-state-in-effect
      if (t) setTitle(t);
      if (c) {
        setContent(nextContent);
        if (editorRef.current) editorRef.current.innerHTML = nextContent;
      }
      if (d) setNoteDomain(d);
    }
  }, [isNew, searchParams]);

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (isNew) {
        const res = await createNote({
          title: title || "未命名笔记", content,
          category: noteCategory, tags: noteTags,
          source_url: noteSourceUrl || null, domain: noteDomain, is_pinned: notePinned,
        });
        return res;
      }
      return updateNote(Number(id), {
        title: title || "未命名笔记", content,
        category: noteCategory, tags: noteTags,
        source_url: noteSourceUrl || null, domain: noteDomain, is_pinned: notePinned,
      });
    },
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ["notes"] });
      message.success("已保存");
      setLastSaved(new Date().toLocaleTimeString("zh-CN"));
      if (isNew && (res as unknown as { id: number }).id) {
        const suffix = noteDomain === "experience" ? "?from=experience" : "";
        navigate(`/notes/${(res as unknown as { id: number }).id}/edit${suffix}`, { replace: true });
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

  const syncEditorContent = useCallback(() => {
    const editor = editorRef.current;
    if (!editor) return;
    setContent(normalizeEditableHtml(editor.innerHTML, editor.textContent));
  }, []);

  const saveEditorSelection = useCallback(() => {
    const editor = editorRef.current;
    const selection = window.getSelection();
    if (!editor || !selection || selection.rangeCount === 0) return;

    const range = selection.getRangeAt(0);
    if (!editor.contains(range.commonAncestorContainer)) return;

    selectionRangeRef.current = range.cloneRange();
    setCurrentBlockType(detectRichBlockType(range, editor));
  }, []);

  const restoreEditorSelection = useCallback(() => {
    const editor = editorRef.current;
    const range = selectionRangeRef.current;
    if (!editor || !range) return;

    const selection = window.getSelection();
    selection?.removeAllRanges();
    selection?.addRange(range);
  }, []);

  const runEditorCommand = useCallback((command: string, value?: string) => {
    const editor = editorRef.current;
    if (!editor) return;

    editor.focus();
    restoreEditorSelection();
    document.execCommand(command, false, value);
    syncEditorContent();
    window.setTimeout(saveEditorSelection, 0);
  }, [restoreEditorSelection, saveEditorSelection, syncEditorContent]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Tab") {
      e.preventDefault();
      runEditorCommand("insertText", "  ");
    }
  }, [runEditorCommand]);

  const applyBlockType = useCallback((type: BlockType) => {
    const blockMap: Record<BlockType, string> = {
      paragraph: "p",
      h1: "h1",
      h2: "h2",
      h3: "h3",
      quote: "blockquote",
      code: "pre",
    };
    runEditorCommand("formatBlock", blockMap[type]);
    setCurrentBlockType(type);
  }, [runEditorCommand]);

  const applyTextColor = useCallback((color: string) => {
    runEditorCommand("foreColor", color);
  }, [runEditorCommand]);

  const applyMarkColor = useCallback((color: string) => {
    runEditorCommand("hiliteColor", color);
  }, [runEditorCommand]);

  const plainContent = useMemo(() => plainTextFromHtml(content), [content]);
  const stats = useMemo(() => countStats(plainContent), [plainContent]);

  const notesByCategory = useMemo(() => {
    const map: Record<string, typeof allNotes> = {};
    for (const n of allNotes || []) {
      const cat = n.category || "未分类";
      if (!map[cat]) map[cat] = [];
      map[cat]!.push(n);
    }
    return map;
  }, [allNotes]);
  const returnPath = searchParams.get("from") === "experience" || noteDomain === "experience"
    ? "/experience"
    : "/notes";

  // 加载中
  if (isLoading) {
    return <Spin style={{ display: "block", textAlign: "center", marginTop: 80 }} />;
  }

  // 加载失败
  if (isError || (!isLoading && !isNew && !note)) {
    return (
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 16 }}>
        <Typography.Text type="secondary">笔记加载失败，可能已被删除</Typography.Text>
        <Button onClick={() => navigate("/notes")}>返回</Button>
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
        <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate(returnPath)}
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
                <div key={n.id} onClick={() => navigate(`/notes/${n.id}/edit${noteDomain === "experience" ? "?from=experience" : ""}`)} style={{
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

        {/* ── 属性栏 ── */}
        <div style={{
          display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap",
          padding: "4px 20px 8px", flexShrink: 0,
        }}>
          {/* 分类 */}
          <Select
            size="small"
            allowClear
            placeholder="分类"
            value={noteCategory}
            onChange={(v) => setNoteCategory(v || null)}
            variant="borderless"
            style={{ fontSize: 12, minWidth: 100 }}
            options={[
              { value: "编程", label: "编程" }, { value: "学习", label: "学习" },
              { value: "生活", label: "生活" }, { value: "工作", label: "工作" },
            ]}
          />
          <span style={{ color: "#e8e8e8" }}>|</span>
          {/* 标签 */}
          <Select
            size="small"
            mode="tags"
            placeholder="标签"
            value={noteTags}
            onChange={(v) => setNoteTags(v)}
            variant="borderless"
            style={{ fontSize: 12, minWidth: 140, flex: 1 }}
          />
          <span style={{ color: "#e8e8e8" }}>|</span>
          {/* 来源 URL */}
          <Popover
            trigger="click"
            open={propsOpen}
            onOpenChange={setPropsOpen}
            content={
              <div style={{ width: 260 }}>
                <div style={{ fontSize: 12, color: "#999", marginBottom: 6 }}>来源 URL</div>
                <Input
                  size="small"
                  value={noteSourceUrl}
                  onChange={(e) => setNoteSourceUrl(e.target.value)}
                  placeholder="原始材料链接"
                  style={{ borderRadius: 6 }}
                />
              </div>
            }
          >
            <Button type="text" size="small" icon={<SettingOutlined />}
              style={{ color: noteSourceUrl ? "#1677ff" : "#ccc", fontSize: 11 }}>
              {noteSourceUrl ? "来源" : ""}
            </Button>
          </Popover>
          {/* 置顶 */}
          <Button
            type="text"
            size="small"
            icon={notePinned ? <PushpinFilled style={{ color: "#fa8c16" }} /> : <PushpinOutlined />}
            onClick={() => setNotePinned(!notePinned)}
            style={{ color: notePinned ? "#fa8c16" : "#ccc", fontSize: 11 }}
          />
        </div>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            padding: "8px 20px",
            borderTop: "1px solid #f3f0ea",
            background: "linear-gradient(90deg, #fffaf0, #ffffff)",
            flexShrink: 0,
          }}
        >
          <Select
            size="small"
            value={currentBlockType}
            onMouseDown={saveEditorSelection}
            onChange={applyBlockType}
            options={[...BLOCK_TYPES]}
            style={{ width: 108 }}
          />
          <Tooltip title="加粗">
            <Button
              size="small"
              type="text"
              icon={<BoldOutlined />}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => runEditorCommand("bold")}
            />
          </Tooltip>
          <Tooltip title="斜体">
            <Button
              size="small"
              type="text"
              icon={<ItalicOutlined />}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => runEditorCommand("italic")}
            />
          </Tooltip>
          <Tooltip title="无序列表">
            <Button
              size="small"
              type="text"
              icon={<UnorderedListOutlined />}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => runEditorCommand("insertUnorderedList")}
            />
          </Tooltip>
          <Tooltip title="有序列表">
            <Button
              size="small"
              type="text"
              icon={<OrderedListOutlined />}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => runEditorCommand("insertOrderedList")}
            />
          </Tooltip>
          <Tooltip title="链接">
            <Button
              size="small"
              type="text"
              icon={<LinkOutlined />}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => {
                const url = window.prompt("输入链接地址", "https://");
                if (url) runEditorCommand("createLink", url);
              }}
            />
          </Tooltip>
          <span style={{ width: 1, height: 20, background: "#eee2cf", margin: "0 4px" }} />
          <Space size={4}>
            <FontColorsOutlined style={{ color: "#9a7b45", fontSize: 13 }} />
            {TEXT_COLORS.map((color) => (
              <Tooltip title="文字颜色" key={color}>
                <button
                  type="button"
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => applyTextColor(color)}
                  style={{
                    width: 18,
                    height: 18,
                    borderRadius: "50%",
                    border: "2px solid #fff",
                    outline: "1px solid rgba(0,0,0,0.12)",
                    background: color,
                    cursor: "pointer",
                  }}
                />
              </Tooltip>
            ))}
          </Space>
          <Space size={4} style={{ marginLeft: 6 }}>
            <HighlightOutlined style={{ color: "#9a7b45", fontSize: 13 }} />
            {MARK_COLORS.map((color) => (
              <Tooltip title="高亮颜色" key={color}>
                <button
                  type="button"
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => applyMarkColor(color)}
                  style={{
                    width: 18,
                    height: 18,
                    borderRadius: 4,
                    border: "1px solid rgba(0,0,0,0.12)",
                    background: color,
                    cursor: "pointer",
                  }}
                />
              </Tooltip>
            ))}
          </Space>
        </div>

        <div style={{ flex: 1, minHeight: 0, position: "relative", borderTop: "1px solid #f0f0f0" }}>
          {!plainContent && (
            <div
              style={{
                position: "absolute",
                top: 22,
                left: 22,
                color: "#b8b0a3",
                pointerEvents: "none",
                fontSize: 15,
              }}
            >
              开始记录。选中文本后可用上方工具栏修改格式和颜色。
            </div>
          )}
          <div
            ref={editorRef}
            className="markdown-preview rich-note-editor"
            contentEditable
            suppressContentEditableWarning
            onInput={syncEditorContent}
            onBlur={syncEditorContent}
            onClick={saveEditorSelection}
            onKeyDown={handleKeyDown}
            onKeyUp={saveEditorSelection}
            onMouseUp={saveEditorSelection}
            style={{
              height: "100%",
              overflow: "auto",
              outline: "none",
              fontSize: 15,
              lineHeight: 1.8,
              padding: "20px 24px 48px",
              background: "linear-gradient(180deg, #fffdf8 0%, #ffffff 38%)",
              color: "#333",
            }}
          />
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
