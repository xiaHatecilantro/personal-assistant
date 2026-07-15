import {
  ClockCircleOutlined,
  PlusOutlined,
  PushpinFilled,
  PushpinOutlined,
} from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { Button, Spin } from "antd";
import { motion } from "motion/react";
import { useNavigate } from "react-router-dom";
import { fetchNotes } from "../api/notes";
import EmptyState from "../components/ui/EmptyState";
import type { Note } from "../types/note";

const noteColors = ["#fff8c7", "#e9f7d4", "#dff3ff", "#ffe7d6", "#f5e6ff"];
const rotations = [-1.4, 0.8, -0.6, 1.2, -1];

function formatDate(value: string) {
  if (!value) return "";
  return new Date(value).toLocaleDateString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
  });
}

function ExperienceCard({ note, index }: { note: Note; index: number }) {
  const navigate = useNavigate();
  const bg = noteColors[index % noteColors.length];
  const rotate = rotations[index % rotations.length];

  return (
    <motion.button
      type="button"
      initial={{ opacity: 0, y: 18, rotate: rotate - 2 }}
      animate={{ opacity: 1, y: 0, rotate }}
      transition={{ duration: 0.32, delay: index * 0.04, ease: [0.25, 1, 0.5, 1] }}
      whileHover={{ y: -6, rotate: 0, boxShadow: "0 18px 32px rgba(64, 45, 20, 0.14)" }}
      onClick={() => navigate(`/notes/${note.id}/edit?from=experience`)}
      style={{
        minHeight: 156,
        border: "1px solid rgba(96, 72, 32, 0.13)",
        borderRadius: 6,
        background: bg,
        padding: "18px 18px 14px",
        textAlign: "left",
        cursor: "pointer",
        boxShadow: "0 10px 20px rgba(64, 45, 20, 0.08)",
        display: "flex",
        flexDirection: "column",
        gap: 14,
        position: "relative",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "linear-gradient(180deg, rgba(255,255,255,0.36), transparent 38%), repeating-linear-gradient(0deg, rgba(255,255,255,0.12) 0 1px, transparent 1px 18px)",
          pointerEvents: "none",
        }}
      />
      <div style={{ position: "relative", display: "flex", alignItems: "flex-start", gap: 10 }}>
        {note.is_pinned ? (
          <PushpinFilled style={{ color: "#d46b08", fontSize: 16, marginTop: 3 }} />
        ) : (
          <PushpinOutlined style={{ color: "rgba(84, 70, 45, 0.32)", fontSize: 16, marginTop: 3 }} />
        )}
        <h3
          style={{
            margin: 0,
            flex: 1,
            color: "#2d281f",
            fontSize: 18,
            lineHeight: 1.35,
            fontWeight: 800,
            wordBreak: "break-word",
          }}
        >
          {note.title}
        </h3>
      </div>

      <div style={{ position: "relative", display: "flex", gap: 6, flexWrap: "wrap", minHeight: 24 }}>
        {note.tags.length > 0 ? (
          note.tags.map((tag) => (
            <span
              key={tag}
              style={{
                fontSize: 12,
                lineHeight: "20px",
                padding: "0 8px",
                borderRadius: 999,
                background: "rgba(255,255,255,0.58)",
                color: "#5d533f",
                border: "1px solid rgba(95,75,45,0.08)",
              }}
            >
              #{tag}
            </span>
          ))
        ) : (
          <span style={{ fontSize: 12, color: "rgba(66, 54, 35, 0.42)" }}>未标记</span>
        )}
      </div>

      <div
        style={{
          marginTop: "auto",
          position: "relative",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          color: "rgba(66, 54, 35, 0.58)",
          fontSize: 12,
          fontWeight: 600,
        }}
      >
        <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
          <ClockCircleOutlined />
          {formatDate(note.updated_at)}
        </span>
        <span>{note.is_pinned ? "已置顶" : "普通"}</span>
      </div>
    </motion.button>
  );
}

export default function ExperiencePage() {
  const navigate = useNavigate();
  const { data: notes, isLoading } = useQuery({
    queryKey: ["notes", { domain: "experience" }],
    queryFn: () => fetchNotes({ domain: "experience" }),
  });

  return (
    <div style={{ maxWidth: 1040, width: "100%", margin: "0 auto", paddingTop: 10, height: "100%", overflow: "auto" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 22 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 26, lineHeight: 1.2, color: "#2a241b", fontWeight: 900 }}>
            经验便签
          </h2>
          <p style={{ margin: "6px 0 0", color: "#8a7c67", fontSize: 13 }}>
            记录走过的路、踩过的坑，以及下次该绕开的地方
          </p>
        </div>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => navigate("/notes/new/edit?domain=experience&from=experience")}
          style={{ borderRadius: 8 }}
        >
          新建便签
        </Button>
      </div>

      <Spin spinning={isLoading}>
        {notes && notes.length > 0 ? (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
              gap: "18px 16px",
              padding: "4px 0 24px",
            }}
          >
            {notes.map((note, index) => (
              <ExperienceCard key={note.id} note={note} index={index} />
            ))}
          </div>
        ) : (
          <EmptyState icon="📌" title="还没有经验便签" hint="把今天踩过的坑先记下来" />
        )}
      </Spin>
    </div>
  );
}
