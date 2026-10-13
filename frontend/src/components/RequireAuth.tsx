/** 模块职责：保护嵌套路由，并通过服务端 /auth/me 复验本地 Token 对应的当前会话。 */

import { useQuery } from "@tanstack/react-query";
import { Spin } from "antd";
import { useEffect } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import client from "../api/client";
import { useAuthStore } from "../store/authStore";


export default function RequireAuth() {
  const location = useLocation();
  const { token, setAuth, logout } = useAuthStore();
  // 本地存在 Token 只代表“可能已登录”；服务端复验用户仍存在且签名、有效期均合法。
  const session = useQuery({
    queryKey: ["auth", "me", token],
    queryFn: () => client.get("/auth/me") as Promise<{ id: number; username: string }>,
    enabled: Boolean(token),
    retry: false,
    staleTime: 60_000,
  });

  useEffect(() => {
    if (token && session.data) setAuth(token, session.data);
  }, [session.data, setAuth, token]);

  useEffect(() => {
    if (session.isError) logout();
  }, [logout, session.isError]);

  if (!token || session.isError) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  if (session.isPending) {
    return <Spin fullscreen tip="正在验证登录状态" />;
  }
  return <Outlet />;
}
