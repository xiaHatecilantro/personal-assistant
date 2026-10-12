/** 模块职责：统一普通 REST 请求的基址、Bearer Token 注入、响应解包和会话失效处理。 */

import axios from "axios";
import { useAuthStore } from "../store/authStore";

const client = axios.create({
  baseURL: "/api/v1",
  timeout: 10000,
  headers: { "Content-Type": "application/json" },
});

client.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

client.interceptors.response.use(
  (res) => res.data,
  (error) => {
    // 服务端 401 表示本地会话已失效，立即统一清除 Token，避免后续请求反复携带旧凭据。
    if (error.response?.status === 401) {
      useAuthStore.getState().logout();
    }
    return Promise.reject(error);
  },
);

export default client;
