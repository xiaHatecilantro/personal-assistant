/** 模块职责：持久化工作区显示信息；浏览器授予的 File 对象仅保存在组件内存中。 */

import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface Workspace {
  name: string;
  path: string;
  addedAt: string;
}

interface WorkspaceState {
  workspaces: Workspace[];
  activePath: string | null;
  addWorkspace: (path: string, name?: string) => void;
  removeWorkspace: (path: string) => void;
  setActive: (path: string | null) => void;
}

export const useWorkspaceStore = create<WorkspaceState>()(
  persist(
    (set) => ({
      workspaces: [],
      activePath: null,
      addWorkspace: (path, nameOverride) => {
        const normalized = path.replace(/\\/g, "/").replace(/\/$/, "");
        const name = nameOverride || normalized.split("/").pop() || normalized;
        set((s) => {
          const exists = s.workspaces.find((w) => w.path === normalized);
          if (exists) return { activePath: normalized };
          return {
            workspaces: [...s.workspaces, { name, path: normalized, addedAt: new Date().toISOString() }],
            activePath: normalized,
          };
        });
      },
      removeWorkspace: (path) =>
        set((s) => ({
          workspaces: s.workspaces.filter((w) => w.path !== path),
          activePath: s.activePath === path ? (s.workspaces[0]?.path || null) : s.activePath,
        })),
      setActive: (path) => set({ activePath: path }),
    }),
    { name: "workspaces" },
  ),
);
