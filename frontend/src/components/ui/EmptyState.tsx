import { Typography } from "antd";
import { motion } from "motion/react";

interface Props {
  icon: string;
  title: string;
  hint?: string;
}

export default function EmptyState({ icon, title, hint }: Props) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.35, ease: [0.25, 1, 0.5, 1] }}
      style={{
        textAlign: "center",
        padding: "64px 20px",
        background: "#fff",
        borderRadius: 20,
        border: "1px solid #f0f0f0",
      }}
    >
      <div style={{ fontSize: 44, marginBottom: 16, opacity: 0.35 }}>{icon}</div>
      <Typography.Text style={{ fontSize: 15, color: "#999", display: "block", marginBottom: 4 }}>
        {title}
      </Typography.Text>
      {hint && (
        <Typography.Text style={{ fontSize: 13, color: "#bbb" }}>
          {hint}
        </Typography.Text>
      )}
    </motion.div>
  );
}
