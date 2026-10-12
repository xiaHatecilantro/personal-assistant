/** 模块职责：保存跨页面认证会话，并统一登录落盘与退出清理。 */

import { create } from "zustand";

interface User {
  id: number;
  username: string;
}

interface AuthState {
  token: string | null;
  user: User | null;
  setAuth: (token: string, user: User) => void;
  logout: () => void;
}

function loadUser(): User | null {
  try {
    return JSON.parse(localStorage.getItem("user") || "null") as User | null;
  } catch {
    localStorage.removeItem("user");
    return null;
  }
}

export const useAuthStore = create<AuthState>((set) => ({
  token: localStorage.getItem("token"),
  user: loadUser(),
  setAuth: (token, user) => {
    localStorage.setItem("token", token);
    localStorage.setItem("user", JSON.stringify(user));
    set({ token, user });
  },
  logout: () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    set({ token: null, user: null });
  },
}));
