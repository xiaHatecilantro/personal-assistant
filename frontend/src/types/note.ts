/** 模块职责：定义后端笔记资源在前端使用的稳定类型。 */

export interface Note {
  id: number;
  owner_id: number;
  title: string;
  content: string;
  category: string | null;
  tags: string[];
  wikilinks: string[];
  source_url: string | null;
  confidence: number | null;
  domain: string | null;
  is_pinned: boolean;
  created_at: string;
  updated_at: string;
}
