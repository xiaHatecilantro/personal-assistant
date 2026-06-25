import { App as AntApp, ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import AppLayout from "./components/AppLayout";
import DashboardPage from "./pages/DashboardPage";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import TaskCreatePage from "./pages/TaskCreatePage";
import NoteCreatePage from "./pages/NoteCreatePage";
import NoteDetailPage from "./pages/NoteDetailPage";
import NotesListPage from "./pages/NotesListPage";
import ChatPage from "./pages/ChatPage";
import TaskDetailPage from "./pages/TaskDetailPage";
import TaskListPage from "./pages/TaskListPage";

const queryClient = new QueryClient();

export default function App() {
  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: "#1677ff",
          borderRadius: 6,
          fontFamily:
            '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Microsoft YaHei", sans-serif',
        },
      }}
    >
      <AntApp>
        <QueryClientProvider client={queryClient}>
          <BrowserRouter>
            <Routes>
              <Route path="login" element={<LoginPage />} />
              <Route path="register" element={<RegisterPage />} />
              <Route element={<AppLayout />}>
                <Route index element={<DashboardPage />} />
                <Route path="tasks" element={<TaskListPage />} />
                <Route path="tasks/new" element={<TaskCreatePage />} />
                <Route path="tasks/:id" element={<TaskDetailPage />} />
                <Route path="notes" element={<NotesListPage />} />
                <Route path="notes/new" element={<NoteCreatePage />} />
                <Route path="notes/:id" element={<NoteDetailPage />} />
                <Route path="chat" element={<ChatPage />} />
              </Route>
            </Routes>
          </BrowserRouter>
        </QueryClientProvider>
      </AntApp>
    </ConfigProvider>
  );
}
