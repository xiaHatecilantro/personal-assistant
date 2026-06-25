import {
  DeleteOutlined,
  EditOutlined,
  LinkOutlined,
  PlusOutlined,
  SearchOutlined,
} from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { App, Button, Empty, Input, List, Popconfirm, Select, Space, Spin, Tag, Typography } from "antd";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { deleteNote, fetchNotes } from "../api/notes";
import type { Note } from "../types/note";

export default function NotesListPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { message } = App.useApp();
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState<string | null>(null);
  const [domain, setDomain] = useState<string | null>(null);

  const { data: notes, isLoading } = useQuery({
    queryKey: ["notes", { search, category, domain }],
    queryFn: () =>
      fetchNotes({
        search: search || undefined,
        category: category || undefined,
        domain: domain || undefined,
      }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteNote(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notes"] });
      message.success("笔记已删除");
    },
  });

  return (
    <>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 20,
        }}
      >
        <Typography.Title level={4} style={{ margin: 0 }}>
          知识库
        </Typography.Title>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => navigate("/notes/new")}
        >
          新建笔记
        </Button>
      </div>

      {/* 搜索 + 筛选 */}
      <div style={{ display: "flex", gap: 12, marginBottom: 20 }}>
        <Input
          placeholder="搜索笔记..."
          prefix={<SearchOutlined />}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          allowClear
          style={{ maxWidth: 300 }}
        />
        <Select
          allowClear
          placeholder="分类"
          style={{ width: 130 }}
          value={category}
          onChange={(v) => setCategory(v || null)}
          options={[
            { value: "编程", label: "编程" },
            { value: "学习", label: "学习" },
            { value: "生活", label: "生活" },
            { value: "工作", label: "工作" },
          ]}
        />
        <Select
          allowClear
          placeholder="领域"
          style={{ width: 130 }}
          value={domain}
          onChange={(v) => setDomain(v || null)}
          options={[
            { value: "Python", label: "Python" },
            { value: "AI", label: "AI" },
            { value: "前端", label: "前端" },
            { value: "后端", label: "后端" },
          ]}
        />
      </div>

      <Spin spinning={isLoading}>
        {notes && notes.length > 0 ? (
          <List
            dataSource={notes}
            renderItem={(note: Note) => (
              <List.Item
                style={{ cursor: "pointer", padding: "12px 16px" }}
                onClick={() => navigate(`/notes/${note.id}`)}
                actions={[
                  <Button
                    key="edit"
                    type="text"
                    size="small"
                    icon={<EditOutlined />}
                    onClick={(e) => {
                      e.stopPropagation();
                      navigate(`/notes/${note.id}`);
                    }}
                  />,
                  <Popconfirm
                    key="del"
                    title="确定删除？"
                    onConfirm={(e) => {
                      e?.stopPropagation();
                      deleteMutation.mutate(note.id);
                    }}
                    onCancel={(e) => e?.stopPropagation()}
                    okText="删除"
                    cancelText="取消"
                  >
                    <Button
                      type="text"
                      danger
                      size="small"
                      icon={<DeleteOutlined />}
                      onClick={(e) => e.stopPropagation()}
                    />
                  </Popconfirm>,
                ]}
              >
                <List.Item.Meta
                  title={
                    <Space>
                      {note.is_pinned && <Tag color="orange">置顶</Tag>}
                      <span>{note.title}</span>
                    </Space>
                  }
                  description={
                    <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
                      {note.category && <Tag>{note.category}</Tag>}
                      {note.domain && <Tag color="geekblue">{note.domain}</Tag>}
                      {note.tags?.map((t: string) => (
                        <Tag key={t} color="default" style={{ fontSize: 11 }}>
                          {t}
                        </Tag>
                      ))}
                      {note.wikilinks?.length > 0 && (
                        <span style={{ fontSize: 12, color: "#999", marginLeft: 8 }}>
                          <LinkOutlined /> {(note.wikilinks as string[]).length} 个关联
                        </span>
                      )}
                      <span style={{ fontSize: 12, color: "#bbb", marginLeft: 8 }}>
                        更新于 {note.updated_at?.slice(0, 10)}
                      </span>
                    </div>
                  }
                />
              </List.Item>
            )}
          />
        ) : (
          <Empty description="还没有笔记，点击上方按钮创建" />
        )}
      </Spin>
    </>
  );
}
