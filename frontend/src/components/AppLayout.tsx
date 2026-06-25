import {
  BookOutlined,
  CheckSquareOutlined,
  DashboardOutlined,
  MessageOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  ScheduleOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { Breadcrumb, Button, Dropdown, Layout, Menu, Space, theme } from "antd";
import { useState, useContext } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "motion/react";
import { ThemeSwitch } from "@lobehub/ui";
import { useAuthStore } from "../store/authStore";
import { ThemeModeContext } from "../App";

const { Sider, Content, Header } = Layout;

const menuItems = [
  { key: "/", icon: <DashboardOutlined />, label: <Link to="/">仪表盘</Link> },
  { key: "/tasks", icon: <CheckSquareOutlined />, label: <Link to="/tasks">任务列表</Link> },
  { key: "/notes", icon: <BookOutlined />, label: <Link to="/notes">知识库</Link> },
  { key: "/chat", icon: <MessageOutlined />, label: <Link to="/chat">AI 对话</Link> },
];

const breadcrumbMap: Record<string, string> = {
  "/": "仪表盘",
  "/tasks": "任务列表",
  "/tasks/new": "新建任务",
  "/notes": "知识库",
  "/notes/new": "新建笔记",
  "/chat": "AI 对话",
};

export default function AppLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const { token } = theme.useToken();
  const { user, logout } = useAuthStore();
  const { themeMode, setThemeMode } = useContext(ThemeModeContext);
  const isDark = themeMode === "dark";

  const pathSnippets = location.pathname.split("/").filter((i) => i);
  const breadcrumbItems = [
    { title: <Link to="/">首页</Link> },
    ...pathSnippets.map((_, index) => {
      const url = `/${pathSnippets.slice(0, index + 1).join("/")}`;
      return { title: breadcrumbMap[url] || url };
    }),
  ];

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider
        trigger={null}
        collapsible
        collapsed={collapsed}
        width={220}
        style={{
          background: token.colorBgContainer,
          borderRight: `1px solid ${token.colorBorderSecondary}`,
        }}
      >
        <div
          style={{
            height: 64,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            borderBottom: `1px solid ${token.colorBorderSecondary}`,
          }}
        >
          <ScheduleOutlined
            style={{ fontSize: collapsed ? 22 : 28, color: token.colorPrimary }}
          />
          {!collapsed && (
            <span
              style={{
                marginLeft: 10,
                fontSize: 17,
                fontWeight: 600,
                color: token.colorTextHeading,
                whiteSpace: "nowrap",
              }}
            >
              个人事务助理
            </span>
          )}
        </div>
        <Menu
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          style={{ border: "none", marginTop: 4 }}
        />
      </Sider>

      <Layout>
        {/* Glass header */}
        <Header
          style={{
            background: isDark
              ? "rgba(20,20,20,0.72)"
              : "rgba(255,255,255,0.72)",
            backdropFilter: "blur(12px)",
            WebkitBackdropFilter: "blur(12px)",
            padding: "0 24px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            height: 56,
            borderBottom: `1px solid ${token.colorBorderSecondary}`,
            position: "sticky",
            top: 0,
            zIndex: 10,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <Button
              type="text"
              icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={() => setCollapsed(!collapsed)}
              style={{ fontSize: 16, width: 40, height: 40 }}
            />
            <Breadcrumb items={breadcrumbItems} />
          </div>
          <Space>
            <ThemeSwitch
              themeMode={themeMode}
              onThemeSwitch={setThemeMode}
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
                      onClick: () => {
                        logout();
                        navigate("/login");
                      },
                    },
                  ],
                }}
              >
                <Button type="text" icon={<UserOutlined />}>
                  {user.username}
                </Button>
              </Dropdown>
            ) : (
              <Button type="link" onClick={() => navigate("/login")}>
                登录
              </Button>
            )}
          </Space>
        </Header>

        <Content
          style={{
            margin: 24,
            padding: 24,
            background: token.colorBgContainer,
            borderRadius: token.borderRadiusLG,
            minHeight: 280,
          }}
        >
          <AnimatePresence mode="wait">
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.18, ease: [0.25, 1, 0.5, 1] }}
              style={{ height: "100%" }}
            >
              <Outlet />
            </motion.div>
          </AnimatePresence>
        </Content>
      </Layout>
    </Layout>
  );
}
