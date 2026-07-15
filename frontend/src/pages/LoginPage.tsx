import { ScheduleOutlined } from "@ant-design/icons";
import { useMutation } from "@tanstack/react-query";
import { App, Button, Checkbox, Form, Input, Typography } from "antd";
import { Link, useNavigate } from "react-router-dom";
import { motion } from "motion/react";
import client from "../api/client";
import { useAuthStore } from "../store/authStore";
import { useContext, useEffect, useRef } from "react";
import { ThemeModeContext } from "../themeModeContext";

interface LoginData {
  username: string;
  password: string;
  rememberPassword?: boolean;
  autoLogin?: boolean;
}

const SAVED_LOGIN_KEY = "saved-login";

interface SavedLogin {
  username: string;
  password: string;
  rememberPassword: boolean;
  autoLogin: boolean;
}

function loadSavedLogin(): SavedLogin | null {
  try {
    return JSON.parse(localStorage.getItem(SAVED_LOGIN_KEY) || "null");
  } catch {
    return null;
  }
}

function saveLoginPreference(data: LoginData) {
  if (!data.rememberPassword) {
    localStorage.removeItem(SAVED_LOGIN_KEY);
    return;
  }
  const saved: SavedLogin = {
    username: data.username,
    password: data.password,
    rememberPassword: true,
    autoLogin: Boolean(data.autoLogin),
  };
  localStorage.setItem(SAVED_LOGIN_KEY, JSON.stringify(saved));
}

export default function LoginPage() {
  const navigate = useNavigate();
  const { token, setAuth } = useAuthStore();
  const { message } = App.useApp();
  const { themeMode } = useContext(ThemeModeContext);
  const isDark = themeMode === "dark";
  const [form] = Form.useForm<LoginData>();
  const autoLoginStarted = useRef(false);
  const savedLogin = loadSavedLogin();

  const mutation = useMutation({
    mutationFn: (data: LoginData) => {
      const { username, password } = data;
      return client.post("/auth/login", { username, password }) as Promise<{ token: string; user: { id: number; username: string } }>;
    },
    onSuccess: (res, variables) => {
      saveLoginPreference(variables);
      setAuth(res.token, res.user);
      message.success("登录成功");
      navigate("/");
    },
    onError: () => { message.error("用户名或密码错误"); },
  });

  useEffect(() => {
    if (token) {
      navigate("/");
    }
  }, [token, navigate]);

  useEffect(() => {
    if (!savedLogin?.autoLogin || autoLoginStarted.current || token) return;
    autoLoginStarted.current = true;
    form.setFieldsValue(savedLogin);
    mutation.mutate(savedLogin);
  }, [form, mutation, savedLogin, token]);

  return (
    <div style={{
      minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center",
      background: isDark
        ? "linear-gradient(135deg, #0d1117 0%, #161b22 50%, #1a2332 100%)"
        : "linear-gradient(135deg, #e8f0fe 0%, #f0f5ff 40%, #fafafa 100%)",
    }}>
      <motion.div
        initial={{ opacity: 0, y: 20, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.5, ease: [0.25, 1, 0.5, 1] }}
        style={{
          width: 400, padding: "40px 36px",
          background: isDark ? "rgba(22,27,34,0.8)" : "rgba(255,255,255,0.8)",
          backdropFilter: "blur(20px)", borderRadius: 24,
          border: `1px solid ${isDark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.06)"}`,
          boxShadow: isDark ? "0 20px 60px rgba(0,0,0,0.4)" : "0 20px 60px rgba(0,0,0,0.08)",
        }}
      >
        {/* Logo */}
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <div style={{
            width: 56, height: 56, borderRadius: 16, background: "linear-gradient(135deg, #1677ff, #4096ff)",
            display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 16px",
            boxShadow: "0 8px 24px rgba(22,119,255,0.25)",
          }}>
            <ScheduleOutlined style={{ fontSize: 28, color: "#fff" }} />
          </div>
          <Typography.Title level={3} style={{ margin: 0, color: isDark ? "#e6edf3" : "#1a1a1a" }}>
            个人事务助理
          </Typography.Title>
        </div>

        <Form
          form={form}
          layout="vertical"
          onFinish={(values) => mutation.mutate(values)}
          onValuesChange={(changedValues) => {
            if (changedValues.rememberPassword === false) {
              form.setFieldValue("autoLogin", false);
            }
          }}
          size="large"
          initialValues={{
            username: savedLogin?.username,
            password: savedLogin?.password,
            rememberPassword: savedLogin?.rememberPassword ?? false,
            autoLogin: savedLogin?.autoLogin ?? false,
          }}
        >
          <Form.Item name="username" rules={[{ required: true, message: "请输入用户名" }]}>
            <Input placeholder="用户名" style={{ borderRadius: 10 }} />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: "请输入密码" }]}>
            <Input.Password placeholder="密码" style={{ borderRadius: 10 }} />
          </Form.Item>
          <Form.Item noStyle shouldUpdate={(prev, next) => prev.rememberPassword !== next.rememberPassword}>
            {({ getFieldValue }) => {
              const rememberPassword = Boolean(getFieldValue("rememberPassword"));
              return (
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 18 }}>
                  <Form.Item name="rememberPassword" valuePropName="checked" noStyle>
                    <Checkbox>记住密码</Checkbox>
                  </Form.Item>
                  <Form.Item name="autoLogin" valuePropName="checked" noStyle>
                    <Checkbox disabled={!rememberPassword}>自动登录</Checkbox>
                  </Form.Item>
                </div>
              );
            }}
          </Form.Item>
          <Form.Item style={{ marginBottom: 8 }}>
            <Button type="primary" htmlType="submit" loading={mutation.isPending} block
              style={{ borderRadius: 10, height: 44, fontSize: 15 }}>
              登录
            </Button>
          </Form.Item>
          <div style={{ textAlign: "center" }}>
            <Typography.Text style={{ fontSize: 13, color: isDark ? "#8b949e" : "#999" }}>
              还没有账号？<Link to="/register" style={{ color: "#1677ff" }}>注册</Link>
            </Typography.Text>
          </div>
        </Form>
      </motion.div>
    </div>
  );
}
