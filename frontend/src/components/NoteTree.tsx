import { FileTextOutlined, FolderOutlined } from "@ant-design/icons";
import { Typography } from "antd";
import { useState } from "react";
import type { Note } from "../types/note";

interface Props {
  notes: Note[];
  onSelect: (note: Note) => void;
}

interface TreeNode {
  name: string;
  type: "folder" | "note";
  children: TreeNode[];
  note?: Note;
  count: number;
}

function buildTree(notes: Note[]): TreeNode[] {
  const root: Record<string, TreeNode> = {};

  for (const n of notes) {
    const category = n.category || "未分类";
    if (!root[category]) {
      root[category] = { name: category, type: "folder", children: [], count: 0 };
    }
    root[category].children.push({
      name: n.title,
      type: "note",
      note: n,
      children: [],
      count: 0,
    });
    root[category].count++;
  }

  return Object.values(root).sort((a, b) => b.count - a.count);
}

export default function NoteTree({ notes, onSelect }: Props) {
  const tree = buildTree(notes);
  const [expanded, setExpanded] = useState<Set<string>>(
    new Set(tree.map((f) => f.name)),
  );

  const toggle = (name: string) =>
    setExpanded((prev) => {
      const n = new Set(prev);
      if (n.has(name)) {
        n.delete(name);
      } else {
        n.add(name);
      }
      return n;
    });

  return (
    <div style={{ userSelect: "none" }}>
      <div
        style={{
          padding: "10px 16px",
          borderBottom: "1px solid #e8e8e8",
          fontSize: 11,
          color: "#999",
          fontWeight: 600,
          textTransform: "uppercase",
          letterSpacing: "0.05em",
        }}
      >
        文件树 · {notes.length} 篇
      </div>

      {tree.map((folder) => {
        const open = expanded.has(folder.name);
        return (
          <div key={folder.name}>
            <div
              onClick={() => toggle(folder.name)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                padding: "6px 16px",
                cursor: "pointer",
                color: "#555",
                fontSize: 13,
                fontWeight: 500,
                transition: "background 0.1s",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "#f0f0f0")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
            >
              <span style={{ fontSize: 10, transition: "transform 0.15s", transform: open ? "rotate(90deg)" : "none" }}>
                ▶
              </span>
              <FolderOutlined style={{ fontSize: 13, color: "#1677ff" }} />
              <span style={{ flex: 1 }}>{folder.name}</span>
              <Typography.Text style={{ fontSize: 11, color: "#bbb" }}>
                {folder.count}
              </Typography.Text>
            </div>

            {open &&
              folder.children.map((child) => (
                <div
                  key={child.note!.id}
                  onClick={() => {
                    setExpanded((p) => {
                      const n = new Set(p);
                      n.add(folder.name);
                      return n;
                    });
                    onSelect(child.note!);
                  }}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    padding: "5px 16px 5px 38px",
                    cursor: "pointer",
                    fontSize: 13,
                    color: "#666",
                    transition: "background 0.1s",
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = "#f5f5f5")}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                >
                  <FileTextOutlined style={{ fontSize: 12, color: "#bbb" }} />
                  <span
                    style={{
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {child.note!.title}
                  </span>
                </div>
              ))}
          </div>
        );
      })}
    </div>
  );
}
