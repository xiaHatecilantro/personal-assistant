import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface ModelConfig {
  id: string;
  name: string;
  provider: string;
  baseUrl: string;
  apiKey: string;
  model: string;
}

interface ModelState {
  models: ModelConfig[];
  activeModelId: string | null;
  addModel: (m: ModelConfig) => void;
  removeModel: (id: string) => void;
  setActive: (id: string) => void;
  updateModel: (id: string, updates: Partial<ModelConfig>) => void;
}

const DEFAULTS: ModelConfig[] = [
  {
    id: "deepseek-default",
    name: "DeepSeek V4",
    provider: "deepseek",
    baseUrl: "https://api.deepseek.com/v1",
    apiKey: "",
    model: "deepseek-chat",
  },
  {
    id: "openai-default",
    name: "OpenAI GPT-4o",
    provider: "openai",
    baseUrl: "https://api.openai.com/v1",
    apiKey: "",
    model: "gpt-4o",
  },
  {
    id: "ollama-default",
    name: "本地 Ollama",
    provider: "ollama",
    baseUrl: "http://localhost:11434/v1",
    apiKey: "",
    model: "qwen2.5:7b",
  },
];

export const useModelStore = create<ModelState>()(
  persist(
    (set) => ({
      models: DEFAULTS,
      activeModelId: "deepseek-default",
      addModel: (m) => set((s) => ({ models: [...s.models, m] })),
      removeModel: (id) =>
        set((s) => {
          const filtered = s.models.filter((m) => m.id !== id);
          return {
            models: filtered,
            activeModelId:
              s.activeModelId === id
                ? filtered[0]?.id || null
                : s.activeModelId,
          };
        }),
      setActive: (id) => set({ activeModelId: id }),
      updateModel: (id, updates) =>
        set((s) => ({
          models: s.models.map((m) => (m.id === id ? { ...m, ...updates } : m)),
        })),
    }),
    { name: "model-config" },
  ),
);
