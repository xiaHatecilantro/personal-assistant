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

const SAVED_LOGIN_KEY = "saved-login";

function disableAutoLogin() {
  try {
    const saved = JSON.parse(localStorage.getItem(SAVED_LOGIN_KEY) || "null");
    if (saved) {
      localStorage.setItem(SAVED_LOGIN_KEY, JSON.stringify({ ...saved, autoLogin: false }));
    }
  } catch {
    localStorage.removeItem(SAVED_LOGIN_KEY);
  }
}

export const useAuthStore = create<AuthState>((set) => ({
  token: localStorage.getItem("token"),
  user: JSON.parse(localStorage.getItem("user") || "null"),
  setAuth: (token, user) => {
    localStorage.setItem("token", token);
    localStorage.setItem("user", JSON.stringify(user));
    set({ token, user });
  },
  logout: () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    disableAutoLogin();
    set({ token: null, user: null });
  },
}));
