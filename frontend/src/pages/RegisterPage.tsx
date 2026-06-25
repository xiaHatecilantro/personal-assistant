import { useMutation } from "@tanstack/react-query";
import { App, Button, Card, Form, Input, Typography } from "antd";
import { Link, useNavigate } from "react-router-dom";
import client from "../api/client";
import { useAuthStore } from "../store/authStore";

interface RegisterData {
  username: string;
  password: string;
}

export default function RegisterPage() {
  const navigate = useNavigate();
  const { setAuth } = useAuthStore();
  const { message } = App.useApp();

  const mutation = useMutation({
    mutationFn: (data: RegisterData) =>
      client.post("/auth/register", data) as Promise<{
        token: string;
        user: { id: number; username: string };
      }>,
    onSuccess: (res) => {
      setAuth(res.token, res.user);
      message.success("注册成功");
      navigate("/");
    },
    onError: (err: any) => {
      const detail = err?.response?.data?.detail;
      message.error(detail || "注册失败");
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
      <Card style={{ width: 380 }} title={<Typography.Title level={4} style={{ margin: 0 }}>注册</Typography.Title>}>
        <Form layout="vertical" onFinish={(values) => mutation.mutate(values)}>
          <Form.Item name="username" label="用户名" rules={[{ required: true, min: 2, max: 50, message: "2-50个字符" }]}>
            <Input placeholder="用户名" />
          </Form.Item>
          <Form.Item name="password" label="密码" rules={[{ required: true, min: 6, message: "至少6位密码" }]}>
            <Input.Password placeholder="密码" />
          </Form.Item>
          <Form.Item
            name="confirm"
            label="确认密码"
            dependencies={["password"]}
            rules={[
              { required: true },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue("password") === value) return Promise.resolve();
                  return Promise.reject(new Error("两次密码不一致"));
                },
              }),
            ]}
          >
            <Input.Password placeholder="确认密码" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={mutation.isPending} block>
              注册
            </Button>
          </Form.Item>
          <div style={{ textAlign: "center" }}>
            已有账号？<Link to="/login">登录</Link>
          </div>
        </Form>
      </Card>
    </div>
  );
}
