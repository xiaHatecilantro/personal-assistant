import axios from "axios";

const client = axios.create({
  baseURL: "/api/v1",
  timeout: 10000,
  headers: { "Content-Type": "application/json" },
});

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
    if (error.response?.status === 401) {
      localStorage.removeItem("token");
      localStorage.removeItem("user");
      disableAutoLogin();
      if (window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  },
);

export default client;
