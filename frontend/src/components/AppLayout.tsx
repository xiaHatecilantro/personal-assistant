import {
  BookOutlined,
  BulbOutlined,
  CheckSquareOutlined,
  DashboardOutlined,
  LogoutOutlined,
  MessageOutlined,
  PlusOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { Button, Dropdown } from "antd";
import { useContext } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "motion/react";
import { ThemeSwitch } from "@lobehub/ui";
import { useAuthStore } from "../store/authStore";
import { ThemeModeContext } from "../themeModeContext";

/* ── 底部 Tab 定义 ── */

const tabs = [
  { path: "/", label: "首页", icon: DashboardOutlined },
  { path: "/chat", label: "对话", icon: MessageOutlined },
  { path: "/notes", label: "知识库", icon: BookOutlined },
  { path: "/experience", label: "经验", icon: BulbOutlined },
  { path: "/tasks", label: "任务", icon: CheckSquareOutlined },
];

/* ── 根据时段生成问候语 ── */

function greet() {
  const h = new Date().getHours();
  if (h < 6) return "夜深了";
  if (h < 9) return "早上好";
  if (h < 12) return "上午好";
  if (h < 14) return "中午好";
  if (h < 18) return "下午好";
  return "晚上好";
}

const todayStr = () =>
  new Date().toLocaleDateString("zh-CN", {
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "long",
  });

/* ── 悬浮 + 按钮 ── */

function FloatingAdd() {
  const navigate = useNavigate();
  return (
    <Dropdown
      trigger={["click"]}
      placement="top"
      menu={{
        items: [
          { key: "task", icon: <CheckSquareOutlined />, label: "新建任务", onClick: () => navigate("/tasks/new") },
          { key: "note", icon: <BookOutlined />, label: "新建笔记", onClick: () => navigate("/notes/new") },
          { key: "experience", icon: <BulbOutlined />, label: "新建便签", onClick: () => navigate("/notes/new/edit?domain=experience&from=experience") },
        ],
      }}
    >
      <button
        style={{
          width: 52,
          height: 52,
          borderRadius: "50%",
          background: "linear-gradient(135deg, #1677ff, #4096ff)",
          border: "none",
          boxShadow: "0 4px 20px rgba(22,119,255,0.35)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          cursor: "pointer",
          transition: "transform 0.2s, box-shadow 0.2s",
        }}
        onMouseEnter={(e) => {
          (e.currentTarget as HTMLButtonElement).style.transform = "scale(1.08)";
          (e.currentTarget as HTMLButtonElement).style.boxShadow = "0 6px 28px rgba(22,119,255,0.45)";
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLButtonElement).style.transform = "scale(1)";
          (e.currentTarget as HTMLButtonElement).style.boxShadow = "0 4px 20px rgba(22,119,255,0.35)";
        }}
      >
        <PlusOutlined style={{ fontSize: 22, color: "#fff" }} />
      </button>
    </Dropdown>
  );
}

/* ═══════════════════════════════════════════ */

export default function AppLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();
  const { themeMode, setThemeMode } = useContext(ThemeModeContext);
  const isDark = themeMode === "dark";

  const showFAB = location.pathname === "/" || location.pathname === "/tasks" || location.pathname === "/experience";

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        background: isDark
          ? "linear-gradient(180deg, #0d1117 0%, #161b22 100%)"
          : "linear-gradient(180deg, #f0f5ff 0%, #fafafa 40%, #fff 100%)",
        transition: "background 0.3s",
      }}
    >
      {/* ── 顶部栏 ── */}
      <header
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "12px 32px",
          flexShrink: 0,
        }}
      >
        {/* 问候 + 日期 */}
        <div>
          <div style={{ fontSize: 20, fontWeight: 700, color: isDark ? "#e6edf3" : "#1a1a1a", lineHeight: 1.3 }}>
            {greet()}，{user?.username || "朋友"}
          </div>
          <div style={{ fontSize: 12, color: isDark ? "#8b949e" : "#999", marginTop: 2 }}>
            {todayStr()}
          </div>
        </div>

        {/* 右侧操作 */}
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <ThemeSwitch
            themeMode={themeMode}
            onThemeSwitch={(mode) => setThemeMode(mode === "dark" ? "dark" : "light")}
          />
          {user ? (
            <Dropdown
              menu={{
                items: [
                  { key: "username", label: user.username, disabled: true },
                  { type: "divider" },
                  {
                    key: "logout",
                    icon: <LogoutOutlined />,
                    label: "退出登录",
                    danger: true,
                    onClick: () => { logout(); navigate("/login"); },
                  },
                ],
              }}
            >
              <Button type="text" shape="circle" icon={<UserOutlined />} />
            </Dropdown>
          ) : (
            <Button type="link" onClick={() => navigate("/login")}>
              登录
            </Button>
          )}
        </div>
      </header>

      {/* ── 内容区 ── */}
      <main
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          minHeight: 0,
          padding: "0 32px 100px",
        }}
      >
        <AnimatePresence mode="wait">
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.2, ease: [0.25, 1, 0.5, 1] }}
            style={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0 }}
          >
            <Outlet />
          </motion.div>
        </AnimatePresence>
      </main>

      {/* ── 悬浮 + 按钮 ── */}
      {showFAB && (
        <div style={{ position: "fixed", bottom: 88, right: 24, zIndex: 50 }}>
          <FloatingAdd />
        </div>
      )}

      {/* ── 底部 TabBar ── */}
      <nav
        style={{
          position: "fixed",
          bottom: 0,
          left: 0,
          right: 0,
          height: 64,
          background: isDark
            ? "rgba(22,27,34,0.88)"
            : "rgba(255,255,255,0.88)",
          backdropFilter: "blur(20px)",
          WebkitBackdropFilter: "blur(20px)",
          borderTop: `1px solid ${isDark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.06)"}`,
          display: "flex",
          justifyContent: "space-around",
          alignItems: "center",
          paddingBottom: "env(safe-area-inset-bottom, 0)",
          zIndex: 40,
        }}
      >
        {tabs.map((t) => {
          const active = t.path === "/" ? location.pathname === "/" : location.pathname.startsWith(t.path);
          const Icon = t.icon;
          return (
            <Link
              key={t.path}
              to={t.path}
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 3,
                textDecoration: "none",
                minWidth: 56,
              }}
            >
              <motion.div
                animate={{
                  scale: active ? 1.1 : 1,
                  color: active ? "#1677ff" : isDark ? "#8b949e" : "#999",
                }}
                transition={{ type: "spring", stiffness: 300, damping: 20 }}
                style={{ display: "flex" }}
              >
                <Icon style={{ fontSize: 22 }} />
              </motion.div>
              <span
                style={{
                  fontSize: 10,
                  fontWeight: active ? 600 : 400,
                  color: active ? "#1677ff" : isDark ? "#8b949e" : "#999",
                  transition: "color 0.2s",
                }}
              >
                {t.label}
              </span>
              {active && (
                <motion.div
                  layoutId="tab-indicator"
                  style={{
                    width: 20,
                    height: 3,
                    borderRadius: 2,
                    background: "#1677ff",
                  }}
                  transition={{ type: "spring", stiffness: 400, damping: 25 }}
                />
              )}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
