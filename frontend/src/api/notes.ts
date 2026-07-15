import client from "./client";
import type { Note } from "../types/note";

export interface KnowledgeIssue {
  type: string;
  page?: string;
  target?: string;
}

export interface KnowledgeGraphNode {
  id: number;
  title: string;
  domain: string | null;
  category: string | null;
}

export interface KnowledgeGraphEdge {
  source: number;
  target: number;
  label: string;
}

export function fetchNotes(params?: {
  category?: string;
  domain?: string;
  tag?: string;
  search?: string;
}): Promise<Note[]> {
  return client.get("/notes", { params });
}

export function fetchNote(id: number): Promise<Note> {
  return client.get(`/notes/${id}`);
}

export function createNote(data: {
  title: string;
  content?: string;
  category?: string | null;
  tags?: string[];
  source_url?: string | null;
  domain?: string | null;
  is_pinned?: boolean;
}): Promise<Note> {
  return client.post("/notes", data);
}

export function updateNote(
  id: number,
  data: {
    title: string;
    content: string;
    category?: string | null;
    tags?: string[];
    source_url?: string | null;
    domain?: string | null;
    is_pinned?: boolean;
  },
): Promise<Note> {
  return client.put(`/notes/${id}`, data);
}

export function deleteNote(id: number): Promise<void> {
  return client.delete(`/notes/${id}`);
}

/** 上传文件解析为 Markdown */
export function importFile(file: File): Promise<{ title: string; content: string; size: number }> {
  const form = new FormData();
  form.append("file", file);
  return client.post("/knowledge/import", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
}

export function ingestSource(data: {
  title: string;
  content: string;
  source_url?: string | null;
}): Promise<{ id: number; content_hash: string; status: string; hint: string }> {
  return client.post("/knowledge/ingest", data);
}

export function compileSource(sourceId: number): Promise<{ status: string; hint: string }> {
  return client.post(`/knowledge/compile/${sourceId}`);
}

export function queryKnowledge(q: string): Promise<{ status: string; query: string; hint: string }> {
  return client.get("/knowledge/query", { params: { q } });
}

export function lintKnowledge(): Promise<{ total_pages: number; issues: KnowledgeIssue[]; hint: string }> {
  return client.post("/knowledge/lint");
}

export function fetchKnowledgeGraph(): Promise<{ nodes: KnowledgeGraphNode[]; edges: KnowledgeGraphEdge[] }> {
  return client.get("/knowledge/graph");
}
