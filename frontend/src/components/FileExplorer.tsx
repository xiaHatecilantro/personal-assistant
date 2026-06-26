import {
  CaretRightOutlined,
  CloseOutlined,
  FileTextOutlined,
  FolderAddOutlined,
  FolderOutlined,
} from "@ant-design/icons";
import { Button, Typography } from "antd";
import { useCallback, useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { useWorkspaceStore } from "../store/workspaceStore";

interface FSNode {
  name: string;
  path: string;
  type: "folder" | "file";
  children?: FSNode[];
  file?: File; // for leaf nodes from webkitdirectory
}

interface Props {
  onSelectFile: (file: File, name: string) => void;
  activeFileName?: string;
}

const EXT_COLORS: Record<string, string> = {
  ts: "#3178c6", tsx: "#61dafb", js: "#f7df1e", jsx: "#61dafb",
  py: "#3776ab", css: "#1572b6", html: "#e34f26", md: "#8c8c8c",
  json: "#f0c040", yml: "#7cb342", yaml: "#7cb342", sql: "#336791",
  rs: "#dea584", go: "#00add8", sh: "#4eaa25", toml: "#9c4221",
};

function extColor(name: string): string {
  const dot = name.lastIndexOf(".");
  if (dot === -1) return "#999";
  return EXT_COLORS[name.slice(dot + 1).toLowerCase()] || "#999";
}

function isBinary(name: string): boolean {
  return /\.(png|jpg|jpeg|gif|ico|exe|dll|zip|tar|gz|pdf|mp4|mp3|ttf|woff2?)$/i.test(name);
}

/** Build a folder tree from flat file list with webkitRelativePath */
function buildTreeFromFiles(files: File[]): { rootName: string; nodes: FSNode[] } {
  const root = files[0]?.webkitRelativePath?.split("/")[0] || "files";
  const tree: FSNode[] = [];

  for (const f of files) {
    const parts = f.webkitRelativePath.split("/");
    if (parts.length === 0) continue;
    // skip root dir name
    let current = tree;
    for (let i = 1; i < parts.length; i++) {
      const name = parts[i];
      const isFile = i === parts.length - 1;
      if (isFile) {
        current.push({ name, path: f.webkitRelativePath, type: "file", file: f });
      } else {
        let folder = current.find((n) => n.name === name && n.type === "folder");
        if (!folder) {
          folder = { name, path: parts.slice(0, i + 1).join("/"), type: "folder", children: [] };
          current.push(folder);
        }
        current = folder.children!;
      }
    }
  }

  // sort
  const sortNodes = (nodes: FSNode[]) => {
    nodes.sort((a, b) => {
      if (a.type !== b.type) return a.type === "folder" ? -1 : 1;
      return a.name.localeCompare(b.name);
    });
    nodes.filter((n) => n.children).forEach((n) => sortNodes(n.children!));
  };
  sortNodes(tree);
  return { rootName: root, nodes: tree };
}

function TreeNode({
  node, depth, onSelectFile, expanded, onToggle, activeFileName,
}: {
  node: FSNode; depth: number;
  onSelectFile: (file: File, name: string) => void;
  expanded: Set<string>; onToggle: (key: string) => void;
  activeFileName?: string;
}) {
  const fullKey = `${depth}-${node.name}`;
  const isOpen = expanded.has(fullKey);
  const isActive = activeFileName === node.name;
  const color = node.type === "folder" ? "#dc8a3c" : extColor(node.name);

  const handleClick = () => {
    if (node.type === "folder") {
      onToggle(fullKey);
    } else if (node.file && !isBinary(node.name)) {
      onSelectFile(node.file, node.name);
    }
  };

  return (
    <div>
      <div
        onClick={handleClick}
        style={{
          display: "flex", alignItems: "center", gap: 2, height: 30,
          paddingLeft: 4 + depth * 16, paddingRight: 6,
          cursor: node.type === "folder" || (!!node.file && !isBinary(node.name)) ? "pointer" : "default",
          fontSize: 13, color: "#555", transition: "background 0.12s",
          userSelect: "none", borderRadius: 8, margin: "1px 6px",
          opacity: node.type === "file" && !node.file ? 0.45 : (isBinary(node.name) ? 0.45 : 1),
          background: isActive ? "#e6f4ff" : "transparent",
        }}
        onMouseEnter={(e) => { if (!isActive) e.currentTarget.style.background = "#f0f0f0"; }}
        onMouseLeave={(e) => { if (!isActive) e.currentTarget.style.background = "transparent"; }}
      >
        {node.type === "folder" ? (
          <span style={{ width: 16, height: 16, display: "inline-flex", alignItems: "center", justifyContent: "center", flexShrink: 0, transition: "transform 0.15s", transform: isOpen ? "rotate(90deg)" : "none" }}>
            <CaretRightOutlined style={{ fontSize: 10, color: "#bbb" }} />
          </span>
        ) : (
          <span style={{ width: 16, flexShrink: 0 }} />
        )}
        <span style={{ width: 18, flexShrink: 0, display: "flex", justifyContent: "center" }}>
          {node.type === "folder"
            ? <FolderOutlined style={{ fontSize: 14, color }} />
            : <FileTextOutlined style={{ fontSize: 13, color }} />}
        </span>
        <Typography.Text ellipsis style={{ fontSize: 13, color: node.type === "folder" ? "#3b3b3b" : "#555", fontWeight: node.type === "folder" ? 500 : 400, flex: 1, minWidth: 0 }}>
          {node.name}
        </Typography.Text>
      </div>
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.12 }}
          >
            {node.children?.map((c, i) => (
              <motion.div
                key={`${fullKey}/${c.name}`}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.15, delay: i * 0.02, ease: [0.25, 1, 0.5, 1] }}
              >
                <TreeNode node={c} depth={depth + 1} onSelectFile={onSelectFile} expanded={expanded} onToggle={onToggle} activeFileName={activeFileName} />
              </motion.div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default function FileExplorer({ onSelectFile, activeFileName }: Props) {
  const { workspaces, activePath, addWorkspace, removeWorkspace, setActive } = useWorkspaceStore();
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const folderInputRef = useRef<HTMLInputElement | null>(null);
  const [treeMap, setTreeMap] = useState<Map<string, FSNode[]>>(new Map());

  // React 会剥离 webkitdirectory 属性，通过原生 DOM 属性写入
  const setFolderRef = useCallback((el: HTMLInputElement | null) => {
    folderInputRef.current = el;
    if (el) {
      (el as HTMLInputElement & { webkitdirectory: boolean }).webkitdirectory = true;
    }
  }, []);

  useEffect(() => {
    if (workspaces.length > 0 && !activePath) {
      setActive(workspaces[0].path);
    }
  }, [workspaces, activePath, setActive]);

  const handlePickFolder = useCallback(() => {
    folderInputRef.current?.click();
  }, []);

  const handleFilesSelected = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;
    const { rootName, nodes } = buildTreeFromFiles(files);
    setTreeMap((prev) => new Map(prev).set(rootName, nodes));
    addWorkspace(rootName);
    // 重置 input 以便可以重新选择同一文件夹
    e.target.value = "";
  }, [addWorkspace]);

  const toggleFolder = useCallback((key: string) => {
    setExpanded((prev) => {
      const n = new Set(prev);
      n.has(key) ? n.delete(key) : n.add(key);
      return n;
    });
  }, []);

  const activeNodes = treeMap.get(activePath || "") || [];

  return (
    <div style={{ userSelect: "none", display: "flex", flexDirection: "column", height: "100%" }}>
      {/* 隐藏的文件夹选择器 — 必须始终挂载在 DOM 中 */}
      <input
        ref={setFolderRef}
        type="file"
        multiple
        style={{ display: "none" }}
        onChange={handleFilesSelected}
      />

      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "8px 12px", borderBottom: "1px solid #e8e8e8",
      }}>
        <Typography.Text style={{ fontSize: 11, fontWeight: 700, color: "#888", letterSpacing: "0.06em", textTransform: "uppercase" }}>
          工作区
        </Typography.Text>
        <Button type="text" size="small" icon={<FolderAddOutlined />} onClick={handlePickFolder}
          style={{ fontSize: 14, color: "#888" }} />
      </div>

      {workspaces.length === 0 ? (
        <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: 20 }}>
          <Typography.Text type="secondary" style={{ fontSize: 12, textAlign: "center", marginBottom: 12 }}>
            打开一个文件夹开始工作
          </Typography.Text>
          <Button size="small" type="primary" icon={<FolderAddOutlined />} onClick={handlePickFolder}>
            打开文件夹
          </Button>
        </div>
      ) : (
        <>
          <div style={{
            display: "flex", overflow: "auto", borderBottom: "1px solid #f0f0f0",
            background: "#fff", flexShrink: 0,
          }}>
            {workspaces.map((ws) => (
              <div
                key={ws.path}
                onClick={() => setActive(ws.path)}
                style={{
                  display: "flex", alignItems: "center", gap: 4,
                  padding: "5px 10px", cursor: "pointer", fontSize: 12,
                  color: activePath === ws.path ? "#333" : "#888",
                  borderBottom: activePath === ws.path ? "2px solid #1677ff" : "2px solid transparent",
                  background: activePath === ws.path ? "#fff" : "transparent",
                  whiteSpace: "nowrap", flexShrink: 0, fontWeight: activePath === ws.path ? 500 : 400,
                }}
              >
                <FolderOutlined style={{ fontSize: 12, color: activePath === ws.path ? "#dc8a3c" : "#bbb" }} />
                <Typography.Text ellipsis style={{ maxWidth: 100, fontSize: 12 }}>
                  {ws.name}
                </Typography.Text>
                <CloseOutlined
                  style={{ fontSize: 10, color: "#ccc", padding: 2 }}
                  onClick={(e) => { e.stopPropagation(); removeWorkspace(ws.path); setTreeMap((prev) => { const n = new Map(prev); n.delete(ws.path); return n; }); }}
                />
              </div>
            ))}
          </div>

          <div style={{ flex: 1, overflow: "auto", paddingTop: 2 }}>
            {activeNodes.map((node) => (
              <TreeNode
                key={node.path}
                node={node} depth={0}
                onSelectFile={onSelectFile}
                expanded={expanded}
                onToggle={toggleFolder}
                activeFileName={activeFileName}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
