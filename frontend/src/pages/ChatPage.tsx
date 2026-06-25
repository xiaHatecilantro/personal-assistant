import {
  SendOutlined,
  SettingOutlined,
} from "@ant-design/icons";
import { useMutation } from "@tanstack/react-query";
import { Button, Input, Select, Typography } from "antd";
import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { askChat } from "../api/chat";
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

export default function ChatPage() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const { models, activeModelId, setActive } = useModelStore();
  const activeModel = models.find((m) => m.id === activeModelId);

  const [selectedFileName, setSelectedFileName] = useState("");
  const [selectedFileContent, setSelectedFileContent] = useState("");

  const chatMutation = useMutation({
    mutationFn: ({ msg, content, path }: { msg: string; content?: string; path?: string }) =>
      askChat(msg, {
        modelConfig: activeModel?.provider ? {
          provider: activeModel.provider,
          baseUrl: activeModel.baseUrl,
          apiKey: activeModel.apiKey,
          model: activeModel.model,
        } : undefined,
        fileContent: content,
        filePath: path,
      }),
    onSuccess: (res) => {
      setMessages((prev) => [
        ...prev,
        { id: Date.now().toString(), role: "assistant", content: res.reply || "收到", time: fmt() },
      ]);
    },
  });

  const send = () => {
    const t = input.trim();
    if (!t || chatMutation.isPending) return;
    setMessages((prev) => [...prev, { id: Date.now().toString(), role: "user", content: t, time: fmt() }]);
    setInput("");
    chatMutation.mutate({ msg: t, content: selectedFileContent, path: selectedFileName });
  };

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const handleSelectFile = async (file: File, name: string) => {
    setSelectedFileName(name);
    try {
      const text = await file.text();
      setSelectedFileContent(text);
      setInput(`请分析以下文件内容（来自 ${name}）：\n\n\`\`\`\n${text.slice(0, 3000)}\n\`\`\``);
    } catch {
      setSelectedFileContent("");
    }
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
            messages.map((msg, idx) => {
              const isUser = msg.role === "user";
              const prev = idx > 0 ? messages[idx - 1] : null;
              return (
                <motion.div
                  key={msg.id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.2, ease: [0.25, 1, 0.5, 1] }}
                >
                  {prev && prev.role !== msg.role && <div style={{ height: 12 }} />}
                  <div
                    style={{
                      padding: "6px 24px",
                      ...(isUser
                        ? {
                            background: "#f8f9fa",
                            borderTop: "1px solid #f0f0f0",
                            borderBottom: "1px solid #f0f0f0",
                          }
                        : {}),
                    }}
                  >
                    <div style={{ maxWidth: 800, margin: "0 auto", display: "flex", gap: 12 }}>
                      <div style={{ width: 44, flexShrink: 0, textAlign: "right" }}>
                        <Typography.Text
                          style={{
                            fontSize: 10,
                            fontWeight: 600,
                            color: isUser ? "#1677ff" : "#999",
                          }}
                        >
                          {isUser ? "你" : "AI"}
                        </Typography.Text>
                      </div>
                      <div
                        style={{
                          flex: 1,
                          fontSize: 14,
                          lineHeight: 1.75,
                          color: "#333",
                          whiteSpace: "pre-wrap",
                          wordBreak: "break-word",
                          minWidth: 0,
                        }}
                      >
                        {msg.content}
                        <span style={{ fontSize: 10, color: "#ccc", marginLeft: 10 }}>
                          {msg.time}
                        </span>
                      </div>
                    </div>
                  </div>
                </motion.div>
              );
            })
          )}

          {chatMutation.isPending && (
            <div style={{ padding: "6px 24px" }}>
              <div style={{ maxWidth: 800, margin: "0 auto", display: "flex", gap: 12 }}>
                <div style={{ width: 44, flexShrink: 0, textAlign: "right" }}>
                  <Typography.Text style={{ fontSize: 10, fontWeight: 600, color: "#999" }}>
                    AI
                  </Typography.Text>
                </div>
                <div style={{ fontSize: 14, color: "#bbb", lineHeight: 1.75 }}>...</div>
              </div>
            </div>
          )}
        </div>

        {/* input */}
        <div
          style={{
            borderTop: "1px solid #e8e8e8",
            padding: "12px 24px 16px",
            background: "#fff",
          }}
        >
          <div style={{ maxWidth: 800, margin: "0 auto" }}>
            <div
              style={{
                display: "flex",
                gap: 8,
                border: "1px solid #d9d9d9",
                borderRadius: 12,
                padding: "4px 4px 4px 14px",
                alignItems: "flex-end",
                background: "#fff",
                transition: "border-color 0.2s",
              }}
              onFocusCapture={(e) => {
                (e.currentTarget as HTMLDivElement).style.borderColor = "#1677ff";
              }}
              onBlurCapture={(e) => {
                (e.currentTarget as HTMLDivElement).style.borderColor = "#d9d9d9";
              }}
            >
              <Input.TextArea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onPressEnter={(e) => {
                  if (!e.shiftKey) {
                    e.preventDefault();
                    send();
                  }
                }}
                placeholder="输入问题，Enter 发送"
                autoSize={{ minRows: 1, maxRows: 5 }}
                variant="borderless"
                style={{
                  flex: 1,
                  fontSize: 14,
                  resize: "none",
                  padding: "6px 0",
                }}
              />
              <Button
                type="primary"
                icon={<SendOutlined />}
                onClick={send}
                loading={chatMutation.isPending}
                disabled={!input.trim()}
                style={{
                  borderRadius: 10,
                  width: 36,
                  height: 36,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                  padding: 0,
                }}
              />
            </div>
          </div>
        </div>
      </div>

      <ModelSettings open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  );
}
