import { createContext } from "react";

export type ThemeMode = "light" | "dark";

export const ThemeModeContext = createContext<{
  themeMode: ThemeMode;
  setThemeMode: (mode: ThemeMode) => void;
}>({ themeMode: "light", setThemeMode: () => {} });
