import {
  DeleteOutlined,
  RobotOutlined,
  SendOutlined,
  SettingOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { Button, Select, Typography } from "antd";
import { ChatItem, ChatInputArea } from "@lobehub/ui/chat";
import { useState, useCallback, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "motion/react";
import { streamChat } from "../api/chat";
import { useModelStore } from "../store/modelStore";
import ModelSettings from "../components/ModelSettings";
import FileExplorer from "../components/FileExplorer";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  time: string;
}

const fmt = () =>
  new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });

/** 呼吸灯 — AI 思考中的三点跳跃动画 */
function BreathingDots() {
  return (
    <div style={{ display: "flex", gap: 4, paddingLeft: 62 }}>
      {[0, 1, 2].map((i) => (
        <motion.div
          key={i}
          style={{ width: 6, height: 6, borderRadius: "50%", background: "#1677ff" }}
          animate={{ opacity: [0.25, 1, 0.25], scale: [0.8, 1.2, 0.8] }}
          transition={{
            duration: 1.2,
            repeat: Infinity,
            delay: i * 0.2,
            ease: "easeInOut",
          }}
        />
      ))}
    </div>
  );
}

export default function ChatPage() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [selectedFileName, setSelectedFileName] = useState("");
  const [selectedFileContent, setSelectedFileContent] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  const { models, activeModelId, setActive } = useModelStore();
  const activeModel = models.find((m) => m.id === activeModelId);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const send = useCallback(async () => {
    const t = input.trim();
    if (!t || loading) return;
    const userMsg: Message = {
      id: Date.now().toString(),
      role: "user",
      content: t,
      time: fmt(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    const assistantId = (Date.now() + 1).toString();
    let msgAdded = false;

    try {
      let content = "";
      for await (const token of streamChat(t, {
        modelConfig: activeModel ? { ...activeModel } : undefined,
        fileContent: selectedFileContent || undefined,
        filePath: selectedFileName || undefined,
      })) {
        if (!msgAdded) {
          setMessages((prev) => [...prev, { id: assistantId, role: "assistant", content: token, time: fmt() }]);
          msgAdded = true;
        } else {
          content += token;
          setMessages((prev) =>
            prev.map((m) => (m.id === assistantId ? { ...m, content } : m)),
          );
        }
      }
      if (!msgAdded) {
        setMessages((prev) => [...prev, { id: assistantId, role: "assistant", content: "", time: fmt() }]);
      } else {
        setMessages((prev) =>
          prev.map((m) => (m.id === assistantId ? { ...m, time: fmt() } : m)),
        );
      }
    } catch (e: unknown) {
      const errMsg = e instanceof Error ? e.message : String(e);
      setMessages((prev) => [...prev, { id: assistantId, role: "assistant", content: `请求失败: ${errMsg}`, time: fmt() }]);
    } finally {
      setLoading(false);
    }
  }, [input, loading, activeModel, selectedFileContent, selectedFileName]);

  const handleSelectFile = async (file: File, name: string) => {
    setSelectedFileName(name);
    try {
      const text = await file.text();
      setSelectedFileContent(text);
      setInput(
        `请分析以下文件内容（来自 ${name}）：\n\n\`\`\`\n${text.slice(0, 3000)}\n\`\`\``,
      );
    } catch {
      setSelectedFileContent("");
    }
  };

  const clearFile = () => {
    setSelectedFileName("");
    setSelectedFileContent("");
  };

  return (
    <div style={{ display: "flex", height: "calc(100vh - 138px)" }}>
      {/* === LEFT: file tree === */}
      <div
        style={{
          width: 260,
          flexShrink: 0,
          borderRight: "1px solid #e8e8e8",
          background: "#fafafa",
          overflow: "auto",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <FileExplorer onSelectFile={handleSelectFile} activeFileName={selectedFileName} />
      </div>

      {/* === RIGHT: chat === */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        {/* top bar */}
        <div
          style={{
            height: 40,
            padding: "0 16px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            borderBottom: "1px solid #e8e8e8",
            background: "#fff",
          }}
        >
          <Select
            size="small"
            value={activeModelId}
            onChange={(v) => setActive(v)}
            variant="borderless"
            popupMatchSelectWidth={false}
            style={{ minWidth: 140, fontSize: 12, color: "#555" }}
            options={models.map((m) => ({
              value: m.id,
              label: (
                <div>
                  <span style={{ fontSize: 13, fontWeight: 500 }}>{m.name}</span>
                  <Typography.Text type="secondary" style={{ fontSize: 11, marginLeft: 8 }}>
                    {m.provider}
                  </Typography.Text>
                </div>
              ),
            }))}
          />
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Button
              type="text"
              size="small"
              icon={<SettingOutlined />}
              onClick={() => setSettingsOpen(true)}
            />
            <Typography.Text
              style={{ fontSize: 11, color: "#ccc", cursor: "pointer" }}
              onClick={() => setMessages([])}
            >
              清空
            </Typography.Text>
          </div>
        </div>

        {/* messages */}
        <div
          ref={scrollRef}
          style={{ flex: 1, overflow: "auto", padding: "16px 0", background: "#fff" }}
        >
          {messages.length === 0 ? (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                height: "100%",
                color: "#ccc",
              }}
            >
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" style={{ marginBottom: 16, opacity: 0.25 }}>
                <path d="M12 2a10 10 0 1010 10A10 10 0 0012 2z" />
                <path d="M8 9a1 1 0 011-1h6a1 1 0 010 2H9a1 1 0 01-1-1zM8 13a1 1 0 011-1h4a1 1 0 010 2H9a1 1 0 01-1-1z" />
              </svg>
              <Typography.Text style={{ fontSize: 14, color: "#bbb" }}>
                从左侧文件树选择笔记，或直接输入问题
              </Typography.Text>
            </div>
          ) : (
            messages.map((msg) => (
              <motion.div
                key={msg.id}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.22, ease: [0.25, 1, 0.5, 1] }}
              >
                <ChatItem
                  avatar={msg.role === "user"
                    ? { avatar: <UserOutlined />, title: "你" }
                    : { avatar: <RobotOutlined />, title: "AI" }}
                  message={msg.content}
                  placement={msg.role === "user" ? "right" : "left"}
                  showTitle
                />
              </motion.div>
            ))
          )}

          {loading && (
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.22, ease: [0.25, 1, 0.5, 1] }}
            >
              <ChatItem
                avatar={{ avatar: <RobotOutlined />, title: "AI" }}
                message=""
                placement="left"
                loading
                showTitle
              />
              <BreathingDots />
            </motion.div>
          )}
        </div>

        {/* input */}
        <div
          style={{
            borderTop: "1px solid #e8e8e8",
            padding: "10px 16px 14px",
            background: "#fff",
          }}
        >
          <AnimatePresence>
            {selectedFileName && (
              <motion.div
                initial={{ opacity: 0, height: 0, marginBottom: 0 }}
                animate={{ opacity: 1, height: "auto", marginBottom: 8 }}
                exit={{ opacity: 0, height: 0, marginBottom: 0 }}
                transition={{ duration: 0.2, ease: [0.25, 1, 0.5, 1] }}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  padding: "4px 10px",
                  background: "#e6f4ff",
                  borderRadius: 6,
                  fontSize: 12,
                  color: "#1677ff",
                  overflow: "hidden",
                }}
              >
                <span style={{ flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {selectedFileName}
                </span>
                <Button type="text" size="small" icon={<DeleteOutlined />} onClick={clearFile}
                  style={{ color: "#999", fontSize: 12 }} />
              </motion.div>
            )}
          </AnimatePresence>
          <ChatInputArea
            value={input}
            onInput={setInput}
            onSend={send}
            loading={loading}
            placeholder="输入问题，Enter 发送"
            bottomAddons={
              <ChatInputArea.ActionBar
                rightAddons={
                  <Button
                    type="primary"
                    icon={<SendOutlined />}
                    onClick={send}
                    loading={loading}
                    disabled={!input.trim()}
                    style={{
                      borderRadius: 10,
                      width: 36,
                      height: 36,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      padding: 0,
                    }}
                  />
                }
              />
            }
          />
        </div>
      </div>

      <ModelSettings open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  );
}
