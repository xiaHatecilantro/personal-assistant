import { App as AntApp, ConfigProvider, Spin, theme } from "antd";
import zhCN from "antd/locale/zh_CN";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { ThemeProvider } from "@lobehub/ui";
import { LazyMotion, domAnimation } from "motion/react";
import { lazy, Suspense, useState } from "react";
import AppLayout from "./components/AppLayout";
import RequireAuth from "./components/RequireAuth";
import { ThemeModeContext, type ThemeMode } from "./themeModeContext";

const ChatPage = lazy(() => import("./pages/ChatPage"));
const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const ExperiencePage = lazy(() => import("./pages/ExperiencePage"));
const LoginPage = lazy(() => import("./pages/LoginPage"));
const NoteCreatePage = lazy(() => import("./pages/NoteCreatePage"));
const NoteDetailPage = lazy(() => import("./pages/NoteDetailPage"));
const NoteEditorPage = lazy(() => import("./pages/NoteEditorPage"));
const NotesListPage = lazy(() => import("./pages/NotesListPage"));
const RegisterPage = lazy(() => import("./pages/RegisterPage"));
const TaskCreatePage = lazy(() => import("./pages/TaskCreatePage"));
const TaskDetailPage = lazy(() => import("./pages/TaskDetailPage"));
const TaskListPage = lazy(() => import("./pages/TaskListPage"));

const queryClient = new QueryClient();

export default function App() {
  const [themeMode, setThemeMode] = useState<ThemeMode>("light");

  return (
    <ThemeModeContext.Provider value={{ themeMode, setThemeMode }}>
      <LazyMotion features={domAnimation}>
        <ThemeProvider
          customTheme={{
            primaryColor: "blue",
            neutralColor: "slate",
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
                  <Suspense fallback={<Spin fullscreen />}>
                    <Routes>
                    <Route path="login" element={<LoginPage />} />
                    <Route path="register" element={<RegisterPage />} />
                    <Route element={<RequireAuth />}>
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
                        <Route path="experience" element={<ExperiencePage />} />
                        <Route path="chat" element={<ChatPage />} />
                      </Route>
                    </Route>
                    </Routes>
                  </Suspense>
                </BrowserRouter>
              </QueryClientProvider>
            </AntApp>
          </ConfigProvider>
        </ThemeProvider>
      </LazyMotion>
    </ThemeModeContext.Provider>
  );
}
