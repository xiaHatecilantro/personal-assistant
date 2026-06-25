import { useMutation } from "@tanstack/react-query";
import { App, Button, Card, Form, Input, Typography } from "antd";
import { Link, useNavigate } from "react-router-dom";
import client from "../api/client";
import { useAuthStore } from "../store/authStore";

interface LoginData {
  username: string;
  password: string;
}

export default function LoginPage() {
  const navigate = useNavigate();
  const { setAuth } = useAuthStore();
  const { message } = App.useApp();

  const mutation = useMutation({
    mutationFn: (data: LoginData) =>
      client.post("/auth/login", data) as Promise<{
        token: string;
        user: { id: number; username: string };
      }>,
    onSuccess: (res) => {
      setAuth(res.token, res.user);
      message.success("登录成功");
      navigate("/");
    },
    onError: () => {
      message.error("用户名或密码错误");
    },
  });

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "#f5f5f5",
      }}
    >
      <Card style={{ width: 380 }} title={<Typography.Title level={4} style={{ margin: 0 }}>登录</Typography.Title>}>
        <Form layout="vertical" onFinish={(values) => mutation.mutate(values)}>
          <Form.Item name="username" label="用户名" rules={[{ required: true, message: "请输入用户名" }]}>
            <Input placeholder="用户名" />
          </Form.Item>
          <Form.Item name="password" label="密码" rules={[{ required: true, message: "请输入密码" }]}>
            <Input.Password placeholder="密码" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={mutation.isPending} block>
              登录
            </Button>
          </Form.Item>
          <div style={{ textAlign: "center" }}>
            还没有账号？<Link to="/register">注册</Link>
          </div>
        </Form>
      </Card>
    </div>
  );
}
