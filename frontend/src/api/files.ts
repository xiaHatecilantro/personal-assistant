import client from "./client";

export interface FileNode {
  name: string;
  path: string;
  type: "folder" | "file";
  children?: FileNode[];
}

export interface RootEntry {
  name: string;
  path: string;
}

export function fetchRoots(): Promise<RootEntry[]> {
  return client.get("/files/roots");
}

export function fetchTree(path: string): Promise<FileNode[]> {
  return client.get("/files/tree", { params: { path } });
}

export function fetchFileContent(path: string): Promise<{
  path: string;
  name: string;
  content: string;
  size: number;
}> {
  return client.get("/files/read", { params: { path } });
}
