import { App as AntApp, ConfigProvider, theme } from "antd";
import zhCN from "antd/locale/zh_CN";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { ThemeProvider } from "@lobehub/ui";
import { LazyMotion, domAnimation } from "motion/react";
import * as m from "motion/react-m";
import { createContext, useState } from "react";
import AppLayout from "./components/AppLayout";
import DashboardPage from "./pages/DashboardPage";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import TaskCreatePage from "./pages/TaskCreatePage";
import NoteCreatePage from "./pages/NoteCreatePage";
import NoteDetailPage from "./pages/NoteDetailPage";
import NotesListPage from "./pages/NotesListPage";
import ChatPage from "./pages/ChatPage";
import NoteEditorPage from "./pages/NoteEditorPage";
import TaskDetailPage from "./pages/TaskDetailPage";
import TaskListPage from "./pages/TaskListPage";

type ThemeMode = "light" | "dark";
export const ThemeModeContext = createContext<{
  themeMode: ThemeMode;
  setThemeMode: (m: ThemeMode) => void;
}>({ themeMode: "light", setThemeMode: () => {} });

const queryClient = new QueryClient();

export default function App() {
  const [themeMode, setThemeMode] = useState<ThemeMode>("light");

  return (
    <ThemeModeContext.Provider value={{ themeMode, setThemeMode }}>
      <LazyMotion features={domAnimation}>
        <ThemeProvider
          customTheme={{
            primaryColor: "#1677ff",
            neutralColor: "#8b8c8b",
          }}
          appearance={themeMode}
        >
          <ConfigProvider
            locale={zhCN}
            theme={{
              algorithm: themeMode === "dark" ? theme.darkAlgorithm : theme.defaultAlgorithm,
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
                      <Route path="notes/new/edit" element={<NoteEditorPage />} />
                      <Route path="notes/:id" element={<NoteDetailPage />} />
                      <Route path="notes/:id/edit" element={<NoteEditorPage />} />
                      <Route path="chat" element={<ChatPage />} />
                    </Route>
                  </Routes>
                </BrowserRouter>
              </QueryClientProvider>
            </AntApp>
          </ConfigProvider>
        </ThemeProvider>
      </LazyMotion>
    </ThemeModeContext.Provider>
  );
}
