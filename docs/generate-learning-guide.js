const fs = require("fs");
const path = require("path");
const {
  AlignmentType,
  BorderStyle,
  Document,
  Footer,
  HeadingLevel,
  LevelFormat,
  Packer,
  PageNumber,
  Paragraph,
  ShadingType,
  Table,
  TableCell,
  TableOfContents,
  TableRow,
  TextRun,
  WidthType,
} = require("docx");

const outputPath = path.join(__dirname, "个人项目全流程学习指导书.docx");

const COLORS = {
  ink: "1F2937",
  muted: "4B5563",
  blue: "2563EB",
  lightBlue: "DBEAFE",
  green: "047857",
  lightGreen: "D1FAE5",
  amber: "B45309",
  lightAmber: "FEF3C7",
  gray: "E5E7EB",
  white: "FFFFFF",
};

function run(text, options = {}) {
  return new TextRun({
    text,
    font: "Microsoft YaHei",
    color: options.color || COLORS.ink,
    size: options.size || 22,
    bold: options.bold || false,
    italics: options.italics || false,
  });
}

function p(text, options = {}) {
  return new Paragraph({
    spacing: { before: options.before || 80, after: options.after || 80, line: 300 },
    alignment: options.alignment || AlignmentType.LEFT,
    children: [run(text, options)],
  });
}

function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 360, after: 180 },
    children: [run(text, { size: 32, bold: true, color: COLORS.blue })],
  });
}

function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 260, after: 140 },
    children: [run(text, { size: 27, bold: true })],
  });
}

function h3(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_3,
    spacing: { before: 180, after: 80 },
    children: [run(text, { size: 24, bold: true, color: COLORS.green })],
  });
}

function bullet(text) {
  return new Paragraph({
    numbering: { reference: "bullet", level: 0 },
    spacing: { before: 45, after: 45, line: 300 },
    children: [run(text)],
  });
}

function numbered(text) {
  return new Paragraph({
    numbering: { reference: "numbered", level: 0 },
    spacing: { before: 45, after: 45, line: 300 },
    children: [run(text)],
  });
}

function code(text) {
  return new Paragraph({
    spacing: { before: 60, after: 60 },
    shading: { fill: "F3F4F6", type: ShadingType.CLEAR },
    border: {
      left: { style: BorderStyle.SINGLE, size: 8, color: COLORS.blue, space: 8 },
    },
    children: [
      new TextRun({
        text,
        font: "Consolas",
        color: "111827",
        size: 20,
      }),
    ],
  });
}

function callout(title, body, fill = COLORS.lightBlue, color = COLORS.blue) {
  return new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [9360],
    rows: [
      new TableRow({
        children: [
          new TableCell({
            width: { size: 9360, type: WidthType.DXA },
            shading: { fill, type: ShadingType.CLEAR },
            borders: {
              top: { style: BorderStyle.SINGLE, size: 1, color: fill },
              bottom: { style: BorderStyle.SINGLE, size: 1, color: fill },
              left: { style: BorderStyle.SINGLE, size: 1, color: fill },
              right: { style: BorderStyle.SINGLE, size: 1, color: fill },
            },
            margins: { top: 160, bottom: 160, left: 180, right: 180 },
            children: [
              new Paragraph({
                spacing: { after: 80 },
                children: [run(title, { bold: true, color, size: 23 })],
              }),
              p(body, { before: 0, after: 0, color: COLORS.ink }),
            ],
          }),
        ],
      }),
    ],
  });
}

function table(headers, rows, widths) {
  const border = { style: BorderStyle.SINGLE, size: 1, color: "D1D5DB" };
  const cell = (text, width, header = false) =>
    new TableCell({
      width: { size: width, type: WidthType.DXA },
      shading: { fill: header ? "E0F2FE" : COLORS.white, type: ShadingType.CLEAR },
      borders: { top: border, bottom: border, left: border, right: border },
      margins: { top: 100, bottom: 100, left: 120, right: 120 },
      children: [
        new Paragraph({
          spacing: { before: 0, after: 0, line: 280 },
          children: [run(text, { bold: header, size: 20 })],
        }),
      ],
    });

  return new Table({
    width: { size: widths.reduce((a, b) => a + b, 0), type: WidthType.DXA },
    columnWidths: widths,
    rows: [
      new TableRow({ children: headers.map((header, index) => cell(header, widths[index], true)) }),
      ...rows.map((row) => new TableRow({ children: row.map((value, index) => cell(value, widths[index])) })),
    ],
  });
}

const children = [
  new Paragraph({
    spacing: { before: 800, after: 240 },
    alignment: AlignmentType.CENTER,
    children: [run("个人项目全流程学习指导书", { size: 42, bold: true, color: COLORS.blue })],
  }),
  new Paragraph({
    spacing: { after: 420 },
    alignment: AlignmentType.CENTER,
    children: [run("从本地开发到 Docker 部署、服务器公网访问的开发能力路线", { size: 24, color: COLORS.muted })],
  }),
  callout(
    "适用对象",
    "你已经完成了一个真实项目的本地开发、代码修复、Docker 化、云服务器部署和公网访问。本文档的目标不是讲给老师听，而是把这个过程整理成一份可执行的自学路线：知道要学什么、学到什么程度、怎么判断自己能否应对日常开发工作。",
    COLORS.lightGreen,
    COLORS.green,
  ),
  p("项目案例：个人事务助理。技术栈包括 React、TypeScript、Vite、FastAPI、SQLAlchemy、MySQL、Alembic、JWT、Docker、Docker Compose、Nginx、腾讯云轻量服务器。"),
  new Paragraph({ children: [new TextRun({ break: 1 })] }),
  new TableOfContents("目录", { hyperlink: true, headingStyleRange: "1-3" }),

  h1("一、学习目标：要达到什么程度"),
  p("日常开发工作的强度，不要求你把每个底层原理都研究透，但要求你能独立完成一个需求从理解、开发、测试、部署到排障的闭环。"),
  h2("合格线：能独立完成小型全栈项目"),
  bullet("能看懂一个前后端分离项目的目录结构，知道每个目录大概负责什么。"),
  bullet("能写常见页面、表单、列表、登录态、接口请求和错误处理。"),
  bullet("能写基本后端 API，包括路由、参数校验、数据库读写、认证鉴权。"),
  bullet("能使用 Git 完成分支、提交、推送、拉取、冲突处理。"),
  bullet("能用 Docker Compose 启动前端、后端、数据库，并看日志定位启动失败。"),
  bullet("能把项目部署到云服务器，通过公网 IP 或域名访问。"),
  h2("工作线：能承受日常业务开发"),
  bullet("看到 bug 能从浏览器、前端请求、后端日志、数据库、容器状态一路排查。"),
  bullet("知道配置和密钥不能写死在代码里，能使用 .env 管理环境变量。"),
  bullet("知道数据库结构变更不能手工乱改，能使用迁移工具管理表结构。"),
  bullet("知道公网部署的基本风险：端口暴露、HTTP 不安全、数据库不应直连公网。"),
  bullet("能把一个需求拆成前端、后端、数据库、部署、测试几个部分。"),
  h2("进阶线：开始像工程师一样设计系统"),
  bullet("能区分临时能跑和长期可维护之间的差异。"),
  bullet("能设计基本的数据权限隔离，避免用户 A 看到用户 B 的数据。"),
  bullet("能理解服务之间的依赖关系，例如后端必须等待 MySQL 就绪。"),
  bullet("能为项目建立基本测试、日志、备份、监控和上线流程。"),

  h1("二、整个项目流程地图"),
  p("一个 Web 项目从 0 到公网访问，大致不是“写代码然后上传”这么简单，而是多个环节串起来的工程流程。"),
  table(
    ["阶段", "你做了什么", "对应能力"],
    [
      ["需求与功能", "确定任务管理、知识库、AI 对话、登录等功能", "产品拆解、页面规划、接口规划"],
      ["前端开发", "React 页面、状态管理、接口请求、登录记忆、自动登录", "组件、路由、状态、表单、请求"],
      ["后端开发", "FastAPI API、用户认证、数据库模型、权限隔离", "路由、数据库、JWT、鉴权"],
      ["数据库", "MySQL 存储用户、任务、笔记、配置等数据", "表结构、关系、迁移、连接配置"],
      ["测试与修复", "修复权限隔离、SSE、Docker 启动等待等问题", "回归测试、日志排查、边界处理"],
      ["Docker 化", "用 Dockerfile 和 docker-compose.yml 统一启动前后端和 MySQL", "镜像、容器、网络、卷、端口"],
      ["云服务器", "腾讯云 Docker CE 镜像、SSH 登录、防火墙放行 80", "Linux、SSH、防火墙、公网 IP"],
      ["公网访问", "通过 http://134.175.219.49 访问前端", "Nginx、端口映射、HTTP"],
      ["后续完善", "域名、HTTPS、备份、监控、CI/CD", "生产化部署能力"],
    ],
    [1500, 4300, 3560],
  ),

  h1("三、知识点总览：必须学、够用即可、知道概念"),
  h2("必须学到能动手的知识"),
  bullet("HTML / CSS / JavaScript：页面结构、样式、交互逻辑，这是所有前端框架的基础。"),
  bullet("TypeScript：类型、接口、泛型基础，至少能看懂类型报错并修复。"),
  bullet("React：组件、props、state、hooks、路由、表单、列表渲染、条件渲染。"),
  bullet("HTTP：GET、POST、PUT、DELETE、状态码、请求头、JSON、跨域。"),
  bullet("FastAPI：路由、依赖注入、Pydantic 校验、异常处理、API 文档。"),
  bullet("SQL / MySQL：表、字段、主键、外键、索引、增删改查、事务基本概念。"),
  bullet("Git：clone、status、add、commit、push、pull、branch、merge、冲突解决。"),
  bullet("Linux 命令：cd、ls、cat、nano、sudo、curl、ss、查看日志、查看端口。"),
  bullet("Docker / Compose：镜像、容器、端口映射、环境变量、volume、network、logs、ps。"),
  h2("够用即可的知识"),
  bullet("Nginx：知道它在这里负责托管前端静态文件，也可以反向代理后端 API。"),
  bullet("Alembic：知道它负责数据库迁移，避免手工建表和改表。"),
  bullet("JWT：知道它是登录令牌，后端用它识别当前用户。"),
  bullet("CORS：知道它是浏览器跨域限制，前后端分离时经常会遇到。"),
  bullet("SSE：知道它适合服务端持续向浏览器推送文本流，例如 AI 流式输出。"),
  bullet("云服务器防火墙：知道端口没放行，即使服务启动了外网也访问不了。"),
  h2("先知道概念，后续再深入"),
  bullet("CI/CD：自动测试、自动构建、自动部署。"),
  bullet("HTTPS / TLS：浏览器安全连接和证书体系。"),
  bullet("CDN：缓存静态资源，提高访问速度。"),
  bullet("对象存储：用于存图片、附件、备份等文件。"),
  bullet("监控告警：CPU、内存、磁盘、接口错误率、服务存活。"),
  bullet("日志系统：集中收集和检索前后端、容器、数据库日志。"),
  bullet("数据库备份与恢复：生产项目必须具备的能力。"),

  h1("四、前端学习路线"),
  h2("你要学到的程度"),
  p("能根据产品需求独立写出页面，能和后端 API 对接，能处理登录态、加载中、失败、空数据、权限跳转等常见场景。"),
  h2("核心知识点"),
  table(
    ["知识点", "基本概念", "掌握标准"],
    [
      ["React 组件", "把页面拆成可复用模块", "能写页面组件、表单组件、列表组件"],
      ["React Router", "前端页面路由", "能实现登录页、首页、详情页跳转"],
      ["状态管理", "保存登录态、用户配置、页面状态", "能使用 Zustand 或同类工具管理全局状态"],
      ["接口请求", "浏览器向后端发送 HTTP 请求", "能封装 axios/fetch，统一带 token"],
      ["表单处理", "输入、校验、提交、错误提示", "能实现登录、创建任务、编辑笔记"],
      ["构建工具", "Vite 负责开发服务器和生产构建", "能运行 dev/build，理解 dist 产物"],
      ["UI 组件库", "Ant Design / Lobe UI 提供现成组件", "能按业务组合组件，不依赖复制粘贴"],
      ["性能基础", "包体积、懒加载、缓存", "知道首屏慢时从资源大小和网络带宽排查"],
    ],
    [1700, 3500, 4160],
  ),
  h2("对应到你的项目"),
  bullet("登录页：涉及表单、接口请求、token 保存、记住密码、自动登录。"),
  bullet("任务页：涉及列表、筛选、状态流转、统计图表。"),
  bullet("知识库：涉及 Markdown、搜索、标签、知识图谱。"),
  bullet("AI 对话：涉及 SSE 流式输出、逐 token 渲染、请求中断和错误处理。"),

  h1("五、后端学习路线"),
  h2("你要学到的程度"),
  p("能写出清晰的 API，知道数据从请求进入后端，到校验、鉴权、数据库读写、返回响应的完整路径。"),
  h2("核心知识点"),
  table(
    ["知识点", "基本概念", "掌握标准"],
    [
      ["FastAPI 路由", "定义 API 地址和处理函数", "能写 CRUD 接口"],
      ["Pydantic", "请求和响应数据校验", "能定义创建、更新、返回模型"],
      ["SQLAlchemy", "用 Python 操作数据库", "能写模型、查询、过滤、提交事务"],
      ["认证鉴权", "判断用户是谁、能访问什么", "能用 JWT 保护接口"],
      ["用户数据隔离", "每个用户只能看自己的数据", "所有查询都按 current_user.id 过滤"],
      ["异常处理", "把错误变成明确的 HTTP 响应", "能返回 401、403、404、422、500"],
      ["配置管理", "不同环境使用不同配置", "能从 .env 读取数据库和密钥"],
      ["API 文档", "FastAPI 自动生成 OpenAPI 文档", "能用 /docs 调试接口"],
    ],
    [1700, 3500, 4160],
  ),
  h2("对应到你的项目"),
  bullet("任务接口：创建、查询、更新、删除任务，并按当前用户隔离。"),
  bullet("笔记接口：搜索、知识库入库、图谱关系、断链检测。"),
  bullet("文件接口：必须登录才能访问，并限制允许访问的目录。"),
  bullet("聊天接口：接收前端请求，调用模型服务，使用 SSE 返回流式结果。"),

  h1("六、数据库与迁移学习路线"),
  h2("你要学到的程度"),
  p("能设计基本表结构，能看懂数据关系，知道线上数据库结构变更必须可追踪、可回滚、可重复执行。"),
  bullet("MySQL：关系型数据库，用表保存结构化数据。"),
  bullet("表结构：用户表、任务表、笔记表、模型配置表等。"),
  bullet("主键：每条记录的唯一标识。"),
  bullet("外键：表示表之间的关系，例如任务属于某个用户。"),
  bullet("索引：提高查询速度，但不是越多越好。"),
  bullet("迁移：用 Alembic 记录数据库结构变化，而不是每台机器手动改表。"),
  bullet("Volume：Docker 里的数据库数据必须放在 volume 中，否则容器删除后数据可能丢失。"),
  h2("你的项目里已经遇到的真实问题"),
  p("后端容器第一次启动时，MySQL 容器虽然已经启动，但数据库还没有准备好接受连接，导致 Alembic 迁移连接失败。解决方式是后端入口脚本等待 MySQL 可连接后再执行迁移。"),

  h1("七、Docker 与服务器部署学习路线"),
  h2("你要学到的程度"),
  p("能把本地项目打包成容器，在服务器上用一条命令启动，并能在服务失败时用日志定位问题。"),
  h2("核心概念"),
  bullet("Dockerfile：描述如何构建一个镜像。"),
  bullet("Image：镜像，是应用运行环境的模板。"),
  bullet("Container：容器，是镜像运行起来的实例。"),
  bullet("docker-compose.yml：描述多个容器如何一起运行。"),
  bullet("Port Mapping：端口映射，例如服务器 80 端口映射到前端容器 80。"),
  bullet("Environment Variables：环境变量，用来注入数据库密码、JWT 密钥等配置。"),
  bullet("Network：Compose 内部服务可以通过服务名互相访问，例如后端访问 mysql:3306。"),
  bullet("Volume：持久化数据，例如 MySQL 数据目录。"),
  bullet("Healthcheck：检查服务是否健康，例如 MySQL 是否能响应。"),
  bullet("Entrypoint：容器启动时执行的脚本，例如等待数据库、执行迁移、启动后端。"),
  h2("你实际执行过的部署命令"),
  code("git clone https://github.com/xiaHatecilantro/personal-assistant.git"),
  code("cd personal-assistant"),
  code("cp .env.example .env"),
  code("nano .env"),
  code("sudo docker compose up -d --build"),
  code("sudo docker compose ps"),
  code("sudo docker compose logs backend"),
  h2("日常排障命令"),
  code("curl -I http://127.0.0.1/"),
  code("sudo ss -lntp | grep ':80'"),
  code("sudo docker compose logs --tail=100 backend"),
  code("sudo docker compose restart backend"),
  code("git pull && sudo docker compose up -d --build"),

  h1("八、从本地到公网访问的完整流程"),
  numbered("本地开发：分别启动前端、后端、数据库，确认功能能在 localhost 正常运行。"),
  numbered("本地测试：运行后端测试、前端 build，确认没有明显错误。"),
  numbered("提交代码：用 Git commit 记录变更，并 push 到 GitHub。"),
  numbered("服务器准备：购买云服务器，选择 Docker CE 镜像，使用 SSH 登录。"),
  numbered("拉取代码：在服务器上 git clone 仓库，进入项目目录。"),
  numbered("配置环境变量：复制 .env.example 为 .env，填写 DB_PASSWORD 和 JWT_SECRET_KEY。"),
  numbered("启动容器：执行 docker compose up -d --build。"),
  numbered("查看状态：用 docker compose ps 确认 frontend、backend、mysql 都是 Up。"),
  numbered("检查端口：确认 80 端口监听，并在云厂商防火墙放行 HTTP 80。"),
  numbered("公网访问：浏览器打开 http://服务器公网IP。"),
  numbered("后续生产化：绑定域名，配置 HTTPS，关闭不必要的公网端口，做备份和监控。"),

  h1("九、你这次项目中已经踩过的坑"),
  table(
    ["问题", "现象", "本质原因", "解决思路"],
    [
      ["目录名打错", "cd personal-assistan 报 No such file", "clone 出来的目录名是 personal-assistant", "用 ls 看真实目录名"],
      ["Docker 权限", "permission denied Docker daemon socket", "当前用户不能直接访问 Docker", "使用 sudo docker compose，或把用户加入 docker 组"],
      ["后端启动失败", "pa-backend Exited", "MySQL 还没准备好，后端先连库失败", "入口脚本等待数据库，再执行迁移"],
      ["外网打不开", "公网 IP 响应超时", "端口、防火墙、服务监听任一环节可能有问题", "从容器状态、curl、ss、防火墙逐层排查"],
      ["网站不安全", "浏览器显示不安全", "使用 HTTP 明文访问，没有 HTTPS 证书", "绑定域名并配置 HTTPS"],
      ["访问慢", "页面加载慢或接口慢", "3Mbps 带宽、包体积、服务器配置、冷启动", "压缩资源、代码分包、升级带宽、CDN"],
    ],
    [1500, 2100, 3000, 2760],
  ),

  h1("十、达到日常开发强度的训练清单"),
  h2("第一阶段：能跑起来"),
  bullet("能在本地启动前端、后端、数据库。"),
  bullet("能注册、登录、创建数据、刷新页面后数据仍然存在。"),
  bullet("能看懂浏览器 Console、Network 面板里的常见错误。"),
  bullet("能用 /docs 调试后端 API。"),
  h2("第二阶段：能改需求"),
  bullet("新增一个字段：从数据库模型、迁移、后端接口、前端表单、列表展示完整改完。"),
  bullet("新增一个页面：路由、菜单、接口、状态、错误提示完整接上。"),
  bullet("新增一个权限限制：未登录不能访问，用户只能访问自己的数据。"),
  h2("第三阶段：能排障"),
  bullet("前端白屏：能查构建、路由、资源、Console 报错。"),
  bullet("接口 401：能查 token、请求头、登录状态、后端鉴权。"),
  bullet("接口 500：能查后端日志、数据库连接、异常堆栈。"),
  bullet("容器退出：能查 docker compose ps 和 logs。"),
  bullet("公网打不开：能查服务监听、端口映射、防火墙、安全组。"),
  h2("第四阶段：能上线维护"),
  bullet("能用 git pull + docker compose up -d --build 更新线上版本。"),
  bullet("能备份 MySQL 数据。"),
  bullet("能配置 HTTPS。"),
  bullet("能关闭不该暴露到公网的端口。"),
  bullet("能保留日志并定位线上问题。"),

  h1("十一、建议学习顺序"),
  numbered("先补 HTTP、Git、Linux、Docker 的基础，因为这些是每天都会用的工具能力。"),
  numbered("再系统学 React 和 TypeScript，目标是能独立写页面和排查前端问题。"),
  numbered("同时学 FastAPI、SQLAlchemy、MySQL，目标是能独立写 CRUD 和登录鉴权。"),
  numbered("接着学 Docker Compose、Nginx、云服务器、防火墙，目标是能独立部署。"),
  numbered("最后补 HTTPS、域名、备份、监控、CI/CD，让项目更接近生产环境。"),

  h1("十二、后续深入点名词清单"),
  p("以下内容不要求现在深入，但你应该知道它们存在，后续遇到项目瓶颈时再学。"),
  bullet("前端：Code Splitting、Lazy Loading、Tree Shaking、Bundle Analyzer、Service Worker、WebSocket。"),
  bullet("后端：Middleware、Dependency Injection、Rate Limit、Background Tasks、Message Queue、Cache。"),
  bullet("数据库：事务隔离级别、慢查询、索引优化、连接池、备份恢复、主从复制。"),
  bullet("安全：XSS、CSRF、SQL Injection、Password Hash、Secret Rotation、Least Privilege。"),
  bullet("部署：Reverse Proxy、TLS Termination、Blue-Green Deployment、Rollback、Container Registry。"),
  bullet("工程化：Lint、Formatter、Pre-commit、Unit Test、Integration Test、E2E Test、CI/CD Pipeline。"),
  bullet("可观测性：Metrics、Tracing、Structured Logging、Alerting、Health Check。"),

  h1("十三、你可以用这个项目做的练习"),
  h2("练习 1：新增任务标签颜色"),
  bullet("数据库任务表新增 tag_color 字段。"),
  bullet("Alembic 新增迁移。"),
  bullet("后端创建和更新任务接口支持该字段。"),
  bullet("前端任务表单和列表展示颜色。"),
  bullet("写测试确认用户 A 不能改用户 B 的任务颜色。"),
  h2("练习 2：隐藏公网数据库端口"),
  bullet("修改 docker-compose.yml，不再把 MySQL 3307 暴露到服务器公网。"),
  bullet("确认后端仍然能通过 Compose 内部网络访问 mysql:3306。"),
  bullet("确认公网无法直接连接数据库。"),
  h2("练习 3：配置 HTTPS"),
  bullet("购买或使用已有域名。"),
  bullet("DNS A 记录解析到服务器公网 IP。"),
  bullet("用 Nginx 和证书工具配置 HTTPS。"),
  bullet("确认浏览器不再显示不安全。"),
  h2("练习 4：做一次线上更新"),
  bullet("本地改一个小功能。"),
  bullet("提交并推送到 GitHub。"),
  bullet("服务器 git pull。"),
  bullet("docker compose up -d --build。"),
  bullet("查看容器状态和浏览器访问结果。"),

  h1("十四、最终判断标准"),
  callout(
    "什么时候算基本具备日常开发能力",
    "当你能独立完成一个小需求，从前端页面、后端接口、数据库迁移、测试验证、Git 提交、Docker 部署、服务器排障全流程走完，并能解释每一步为什么这么做，就已经达到初级日常开发工作的基本强度。",
    COLORS.lightAmber,
    COLORS.amber,
  ),
  p("不要追求一次性学完所有技术。正确路径是：用项目驱动学习，遇到问题时沿着前端、后端、数据库、容器、服务器这条链路定位。你已经走过一次完整链路，下一步应该把每个环节变成可重复执行的能力。"),

  h1("十五、直接学习规划"),
  p("下面这份规划按 8 周设计。目标不是把所有技术都学到精通，而是先达到能完成日常开发任务的强度：能开发、能联调、能部署、能排障、能解释自己的改动。"),
  table(
    ["阶段", "学习重点", "要达到的程度", "验收任务"],
    [
      ["第 1 周", "Git、命令行、HTTP、浏览器调试", "能熟练使用常见命令，能看懂 Network 请求和常见状态码", "本地启动项目，完成一次代码修改、commit、push，并用 Network 面板解释登录请求"],
      ["第 2 周", "JavaScript、TypeScript、React 基础", "能写组件、props、state、hooks、路由和表单", "新增一个简单页面，并接入菜单和路由"],
      ["第 3 周", "前端接口联调和状态管理", "能封装请求，处理 token、加载中、错误提示、空状态", "给一个页面补完整的 loading、error、empty 状态"],
      ["第 4 周", "FastAPI、Pydantic、SQLAlchemy", "能写 CRUD API，能理解请求校验、数据库查询和响应结构", "新增一个后端资源接口，并用 /docs 调通"],
      ["第 5 周", "MySQL、表结构、Alembic 迁移", "能新增字段、写迁移、更新模型和接口", "给任务新增一个字段，从数据库到前端完整打通"],
      ["第 6 周", "登录认证、JWT、权限隔离、安全基础", "能保护接口，确保用户只能访问自己的数据", "写一个测试证明用户 A 不能访问用户 B 的任务或笔记"],
      ["第 7 周", "Docker、Docker Compose、Nginx", "能用 compose 启动前端、后端、数据库，并用日志排查失败", "删除本地容器后重新构建启动，确认项目仍能正常访问"],
      ["第 8 周", "云服务器部署、域名、HTTPS、备份和更新流程", "能把项目部署到公网，并知道如何更新、回滚和排障", "完成一次线上更新，并写出从 git pull 到 docker compose up 的部署记录"],
    ],
    [1200, 2500, 2800, 2860],
  ),
  h2("每天怎么学"),
  bullet("每天先用 20 分钟补一个基础概念，例如 HTTP、JWT、Docker volume、Alembic migration。"),
  bullet("再用 60 到 90 分钟在这个项目里做一个小改动，必须真实运行验证。"),
  bullet("最后用 10 分钟记录今天遇到的问题、解决方法和还没懂的关键词。"),
  h2("每周怎么复盘"),
  bullet("能不能不用看教程复现本周操作。"),
  bullet("能不能解释这个改动涉及前端、后端、数据库、部署中的哪些部分。"),
  bullet("能不能在出错时找到第一条有效日志或错误信息。"),
  bullet("能不能把解决过程写成 5 到 10 行笔记，方便下次复用。"),
  h2("学习优先级"),
  numbered("第一优先级：Git、HTTP、浏览器调试、Linux 命令、Docker 日志。这些决定你能不能独立排障。"),
  numbered("第二优先级：React、TypeScript、FastAPI、SQLAlchemy、MySQL。这些决定你能不能完成业务开发。"),
  numbered("第三优先级：Alembic、JWT、Nginx、Docker Compose、服务器防火墙。这些决定你能不能稳定部署。"),
  numbered("第四优先级：HTTPS、备份、监控、CI/CD、性能优化。这些决定项目能不能接近生产可用。"),
  h2("什么时候可以进入下一个阶段"),
  p("如果你能在不依赖我一步步指挥的情况下，独立完成“新增一个字段或页面、写好接口、更新数据库迁移、本地验证、提交代码、服务器部署、排查线上问题”这一整套流程，就说明你已经具备初级日常开发的基本工作强度。之后再深入某个方向，例如前端工程化、后端架构、数据库优化或 DevOps。"),
];

const doc = new Document({
  styles: {
    default: {
      document: {
        run: { font: "Microsoft YaHei", size: 22, color: COLORS.ink },
        paragraph: { spacing: { line: 300 } },
      },
    },
    paragraphStyles: [
      {
        id: "Heading1",
        name: "Heading 1",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { size: 32, bold: true, font: "Microsoft YaHei", color: COLORS.blue },
        paragraph: { spacing: { before: 360, after: 180 }, outlineLevel: 0 },
      },
      {
        id: "Heading2",
        name: "Heading 2",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { size: 27, bold: true, font: "Microsoft YaHei", color: COLORS.ink },
        paragraph: { spacing: { before: 260, after: 140 }, outlineLevel: 1 },
      },
      {
        id: "Heading3",
        name: "Heading 3",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { size: 24, bold: true, font: "Microsoft YaHei", color: COLORS.green },
        paragraph: { spacing: { before: 180, after: 80 }, outlineLevel: 2 },
      },
    ],
  },
  numbering: {
    config: [
      {
        reference: "bullet",
        levels: [
          {
            level: 0,
            format: LevelFormat.BULLET,
            text: "•",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 520, hanging: 260 } } },
          },
        ],
      },
      {
        reference: "numbered",
        levels: [
          {
            level: 0,
            format: LevelFormat.DECIMAL,
            text: "%1.",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 560, hanging: 300 } } },
          },
        ],
      },
    ],
  },
  sections: [
    {
      properties: {
        page: {
          size: { width: 12240, height: 15840 },
          margin: { top: 1080, right: 1440, bottom: 1080, left: 1440 },
        },
      },
      footers: {
        default: new Footer({
          children: [
            new Paragraph({
              alignment: AlignmentType.CENTER,
              children: [
                run("个人项目全流程学习指导书  |  第 ", { size: 18, color: COLORS.muted }),
                new TextRun({ children: [PageNumber.CURRENT], font: "Microsoft YaHei", size: 18, color: COLORS.muted }),
                run(" 页", { size: 18, color: COLORS.muted }),
              ],
            }),
          ],
        }),
      },
      children,
    },
  ],
});

Packer.toBuffer(doc).then((buffer) => {
  fs.writeFileSync(outputPath, buffer);
  console.log(outputPath);
});
