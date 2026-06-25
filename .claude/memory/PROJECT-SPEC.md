# PROJECT-SPEC: 个人事务助理

> 最后更新：2026-06-10
> 状态：MVP 开发中

## 项目概述

一个 Web 端个人事务助理应用，帮助用户管理待办任务、追踪完成效率，后续扩展知识库等模块。

**目标岗位**：后端/全栈开发实习

## 技术栈

| 层次 | 技术 |
|:---|:---|
| 前端 | React 18 + Vite + TypeScript + Ant Design |
| 状态管理 | Zustand（客户端状态） + TanStack Query（服务端状态） |
| 路由 | React Router v6 |
| 图表 | Recharts |
| 后端 | Python FastAPI + SQLAlchemy 2.0 |
| 数据库 | MySQL 8.0 |
| 部署 Phase 1 | 前端 Vercel + 后端 Render + PlanetScale（免费 MySQL） |
| 部署 Phase 2 | Docker Compose（FastAPI + MySQL + Nginx）→ 阿里云学生服务器 |

## 部署策略（两阶段演进）

**Phase 1 — Vercel + Render + PlanetScale（快速验证）**
- 目的：快速上线可演示的版本，面试时能直接给链接
- 前端 Vercel，后端 Render，数据库 PlanetScale 免费版
- 三者免费额度足够 MVP 使用

**Phase 2 — Docker Compose → 阿里云学生机（容器化实践）** ★
- 目的：学习 Docker 容器化，体现运维能力
- 把 FastAPI + MySQL + Nginx 打包进 `docker-compose.yml`
- 部署到阿里云学生服务器（约 9.9 元/月）
- 实现一键部署 + 环境一致性
- 简历亮点：经历过从 Serverless 到自托管容器的完整演进

## 架构决策

- **前后端分离**：React SPA + FastAPI RESTful API，HTTP JSON 通信
- **无认证（MVP）**：固定 owner_id=1，接口保留 owner_id 字段，后续加 JWT 只需加 Depends
- **服务端状态全交 TanStack Query**：缓存、自动刷新、乐观更新，不手写 useEffect+fetch
- **组件库用 Ant Design**：减少 CSS 工作量，聚焦业务逻辑
- **数据库建表预留扩展字段**：tasks 表预留 owner_id，notes 表在 Phase 3 创建

## 数据库设计

### Phase 1 — MVP 表

```sql
CREATE TABLE tasks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    owner_id INT NOT NULL DEFAULT 1 COMMENT '预留多用户，MVP固定为1',
    title VARCHAR(200) NOT NULL,
    description TEXT,
    priority ENUM('high','medium','low') NOT NULL DEFAULT 'medium',
    status ENUM('todo','in_progress','done') NOT NULL DEFAULT 'todo',
    due_date DATE,
    tag VARCHAR(50) COMMENT '分类标签，如 工作/学习/生活',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_owner_status (owner_id, status),
    INDEX idx_owner_priority (owner_id, priority),
    INDEX idx_owner_due (owner_id, due_date),
    INDEX idx_owner_tag (owner_id, tag)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### Phase 2 — 认证预留

```sql
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### Phase 3 — 知识库预留 ★

```sql
CREATE TABLE notes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    owner_id INT NOT NULL,
    title VARCHAR(200) NOT NULL,
    content MEDIUMTEXT,
    category VARCHAR(50) COMMENT '自定义分类',
    tags JSON COMMENT '标签数组',
    is_pinned TINYINT(1) NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_owner_category (owner_id, category),
    INDEX idx_owner_pinned (owner_id, is_pinned)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

> ★ 知识库是用户强调要预留的功能：笔记 CRUD、分类/标签检索、置顶、全文搜索。Phase 3 时创建此表，当前设计仅作预留。

## API 设计

Base: `http://localhost:8000/api/v1`

| 方法 | 路径 | 说明 |
|:---|:---|:---|
| GET | /tasks | 列表，支持 ?status=&priority=&tag=&page=&page_size= |
| POST | /tasks | 创建 |
| GET | /tasks/{id} | 详情 |
| PUT | /tasks/{id} | 更新 |
| DELETE | /tasks/{id} | 删除 |
| GET | /tasks/stats/overview | 统计概览（总数、各状态数量、各优先级分布） |
| GET | /tasks/stats/trend | 近7天每日完成数 |

```json
// POST /tasks
{
    "title": "完成数据结构作业",
    "description": "第三章课后习题",
    "priority": "high",
    "status": "todo",
    "due_date": "2026-06-15",
    "tag": "学习"
}

// GET /tasks/stats/overview
{
    "total": 25,
    "by_status": {"todo": 10, "in_progress": 5, "done": 10},
    "by_priority": {"high": 5, "medium": 12, "low": 8}
}

// GET /tasks/stats/trend
{
    "daily_completed": [
        {"date": "2026-06-04", "count": 3},
        {"date": "2026-06-05", "count": 5}
    ]
}
```

## 前端路由 & 组件

```
/            → DashboardPage （统计卡片 + 近7天趋势图 + 优先级饼图）
/tasks       → TaskListPage  （筛选栏 + 分页表格）
/tasks/new   → TaskCreatePage（新建表单）
/tasks/:id   → TaskDetailPage（详情 + 编辑模式）
```

```
App
├── AppLayout (Sider 导航 + Content)
│   ├── DashboardPage
│   │   ├── StatCard × 3
│   │   ├── WeeklyTrendChart (Recharts)
│   │   └── PriorityPieChart
│   ├── TaskListPage
│   │   ├── TaskFilterBar
│   │   └── TaskTable (Ant Table + 分页)
│   ├── TaskCreatePage
│   │   └── TaskForm
│   └── TaskDetailPage
│       ├── TaskForm (编辑)
│       └── 状态切换 / 删除按钮
```

## 开发阶段

### 第一阶段 — 项目骨架搭建 ✅（2026-06-10 完成）

- [x] FastAPI 后端初始化 + 健康检查接口
- [x] Docker MySQL 8.0 启动 + 数据库/表创建
- [x] SQLAlchemy Task 模型定义 + 自动建表
- [x] React + TypeScript + Vite 前端初始化
- [x] Ant Design 布局框架 + 前后端联通验证

> 详细总结见下方 [第一阶段总结](#第一阶段总结)

### 第二阶段 — Task CRUD（当前）

- [ ] 后端：POST /tasks 创建任务
- [ ] 后端：PUT /tasks/{id} 更新任务
- [ ] 后端：DELETE /tasks/{id} 删除任务
- [ ] 后端：GET /tasks/{id} 单个任务详情
- [ ] 后端：Pydantic Schema 请求校验
- [ ] 前端：TaskCreatePage 新建表单
- [ ] 前端：TaskDetailPage 详情 + 编辑
- [ ] 前端：TanStack Query useMutation 对接增删改

### 第三阶段 — 筛选 + 仪表盘

- [ ] 后端：GET /tasks 支持 ?status=&priority=&tag=&page=&page_size=
- [ ] 前端：TaskFilterBar 筛选组件
- [ ] 前端：Ant Table 分页
- [ ] 后端：GET /tasks/stats/overview + /tasks/stats/trend
- [ ] 前端：Dashboard 统计卡片 + Recharts 趋势图 + 饼图

### 第四阶段 — 容器化部署

- [ ] Docker Compose（FastAPI + MySQL + Nginx）
- [ ] 阿里云学生服务器部署
- [ ] 线上可演示链接

### 后续阶段

- [ ] 认证（JWT 注册/登录）
- [ ] 知识库（笔记 CRUD + 全文搜索 + Markdown）
- [ ] 增强功能（截止日提醒、日历视图、数据导出）

## 项目结构

```
personal-assistant/
├── CLAUDE.md
├── .claude/
│   ├── agents/          # SeekFlow 代理
│   ├── skills/          # SeekFlow 技能
│   ├── hooks/           # SeekFlow 钩子
│   ├── rules/           # 编码/测试/DeepSeek 规范
│   ├── learned/         # 负反馈学习记录（自动生成）
│   └── memory/
│       ├── MEMORY.md    # 决策记录
│       └── PROJECT-SPEC.md
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   └── routers/
│   │       └── tasks.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/tasks.ts
│   │   ├── types/task.ts
│   │   ├── store/filterStore.ts
│   │   ├── pages/
│   │   │   ├── DashboardPage.tsx
│   │   │   ├── TaskListPage.tsx
│   │   │   ├── TaskCreatePage.tsx
│   │   │   └── TaskDetailPage.tsx
│   │   ├── components/
│   │   │   ├── AppLayout.tsx
│   │   │   ├── TaskForm.tsx
│   │   │   └── StatCard.tsx
│   │   ├── App.tsx
│   │   └── main.tsx
│   └── package.json
├── docker-compose.yml   # Phase 4
├── nginx.conf           # Phase 4
└── .env.example
```
