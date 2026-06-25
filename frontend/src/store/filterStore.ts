import { create } from "zustand";

interface FilterState {
  status: string | null;
  priority: string | null;
  tag: string | null;
  page: number;
  setStatus: (s: string | null) => void;
  setPriority: (p: string | null) => void;
  setTag: (t: string | null) => void;
  setPage: (p: number) => void;
  reset: () => void;
}

export const useFilterStore = create<FilterState>((set) => ({
  status: null,
  priority: null,
  tag: null,
  page: 1,
  setStatus: (status) => set({ status, page: 1 }),
  setPriority: (priority) => set({ priority, page: 1 }),
  setTag: (tag) => set({ tag, page: 1 }),
  setPage: (page) => set({ page }),
  reset: () => set({ status: null, priority: null, tag: null, page: 1 }),
}));
