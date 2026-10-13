import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    // 独立进程避免 Node 20 VM runner 对依赖 ESM 与动态导入的限制。
    pool: "forks",
    maxWorkers: 1,
    fileParallelism: false,
  },
});
