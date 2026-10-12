/** 模块职责：在应用组件树中共享明暗主题模式及切换函数。 */

import { createContext } from "react";

export type ThemeMode = "light" | "dark";

export const ThemeModeContext = createContext<{
  themeMode: ThemeMode;
  setThemeMode: (mode: ThemeMode) => void;
}>({ themeMode: "light", setThemeMode: () => {} });
