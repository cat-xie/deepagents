# DeepAgents 研究写作协作系统

基于 [deepagents](https://github.com/langchain-ai/deepagents) 框架的多 Agent 协作系统，主 Agent 协调研究员和作家两个子 Agent 完成调研写作任务。支持 Docker 沙箱隔离、人工审批（HITL）、自评循环、持久化记忆等企业级能力。

## 架构

```
┌─────────────────────────────────────────────────────────────┐
│                      主 Agent（研究协调员）                    │
│  职责：根据任务复杂度选择路径，协调子 Agent，管理产出物       │
├─────────────────────────────────────────────────────────────┤
│  路径 A（简单任务）           │  路径 B（复杂任务）            │
│  直接 write_file 写产出       │  write_todos → 委派研究员      │
│  不调用子 Agent               │  → 委派作家 → write_file       │
├───────────────────────────────┴───────────────────────────────┤
│  子 Agent                                                      │
│  ├── 研究员（researcher）：用 Tavily 搜索，记录到 Store         │
│  └── 作家（writer）：基于研究员结果撰写内容，记录到 Store       │
├──────────────────────────────────────────────────────────────┤
│  中间件栈（Middleware）                                       │
│  ├── TodoListMiddleware    ：任务分解与进度跟踪                │
│  ├── RubricMiddleware      ：自评循环（不达标自动返工）         │
│  └── HumanInTheLoop       ：write_file / edit_file 审批        │
├──────────────────────────────────────────────────────────────┤
│  后端与存储                                                    │
│  ├── FilesystemBackend      ：非沙箱模式，写本地磁盘            │
│  ├── DockerSandboxBackend   ：沙箱模式，容器隔离 + execute 工具 │
│  ├── SqliteSaver           ：对话历史 / 中断现场 / todo 持久化  │
│  └── SqliteStore           ：跨会话长期记忆（研究员/作家记忆）  │
└──────────────────────────────────────────────────────────────┘
```

## 技术栈

| 模块 | 技术 |
|------|------|
| Agent 框架 | deepagents（LangChain 出品） |
| LLM 模型 | 阿里百炼 qwen3.8-max（DashScope 兼容模式） |
| 搜索工具 | Tavily Search API |
| 持久化 | SQLite（checkpointer + 自实现 BaseStore） |
| 沙箱 | Docker + 自实现 BaseSandbox |
| 权限控制 | FilesystemPermission（allow / deny / interrupt 三态） |

## 核心功能

### 1. 双路径任务分流
- **路径 A（简单任务）**：写笑话、写诗、生成示例 → 主 Agent 直接 write_file，不调用子 Agent
- **路径 B（复杂任务）**：调研 + 写报告 → write_todos 分解任务 → 委派研究员搜索 → 委派作家撰写 → write_file 保存

### 2. Human-in-the-Loop 人工审批（HITL）
- `interrupt_on` + `stream()` 事件循环实现中断恢复
- agent 调 write_file / edit_file 时暂停，终端弹出审批提示
- 支持 approve / reject 决策

### 3. 权限控制（非沙箱模式）
- `FilesystemPermission` 按 path 模式匹配
- 三态控制：`allow`（放行）/ `deny`（直接拒绝）/ `interrupt`（弹审批）
- 规则示例：output/ 放行、memories/ 禁止、AGENTS.md 审批

### 4. 自评循环（RubricMiddleware）
- agent 写完后 grader 子 Agent 按 rubric 标准打分
- 不达标自动返工，最多重试 `max_iterations` 次
- 状态：`satisfied` / `needs_revision` / `max_iterations_reached`

### 5. 任务管理（TodoListMiddleware）
- agent 自主用 `write_todos` 工具分解复杂任务
- 终端实时显示任务清单和状态流转（pending → in_progress → completed）

### 6. Docker 沙箱隔离
- 自实现 `BaseSandbox` 协议（execute / upload_files / download_files）
- agent 的 `execute` 工具能跑任意 shell 命令，但隔离在容器内
- 支持：内存限制、CPU 限制、网络隔离、资源清理

### 7. 持久化记忆
- **会话内记忆**（SqliteSaver）：对话历史、中断现场、todo 状态、Rubric 迭代记录
- **跨会话记忆**（自实现 SqliteStore）：研究员搜过什么、作家写过什么
- 重启后对话可继续，记忆不丢

## 项目结构

```
my-deep-agent/
├── agent.py                      # 主 Agent 入口
├── api/
│   ├── __init__.py
│   └── server.py                 # FastAPI 后端服务（REST + WebSocket）
├── frontend/                     # React + TypeScript + Vite 前端
│   ├── src/
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
├── subagents/
│   ├── researcher_agent.py       # 研究员子 Agent
│   └── writer_agent.py           # 作家子 Agent
├── skills/
│   ├── researcher_skill.py       # 研究员工具（Tavily 搜索 + Store 记忆）
│   └── writer_skill.py           # 作家工具（撰写 + Store 记忆）
├── stores/
│   ├── sqlite_store.py           # 自实现 BaseStore（SQLite + FTS5 全文检索）
│   └── store_singleton.py        # Store 全局单例
├── backends/
│   ├── __init__.py
│   └── docker_sandbox.py         # Docker 沙箱后端
├── .env.example                  # 环境变量示例
├── .gitignore
├── AGENTS.md                     # Agent 协作规范
├── requirements.txt              # Python 依赖
└── README.md
```

## 快速开始

### 1. 环境准备

```bash
# 克隆项目
git clone https://github.com/your-username/your-repo.git
cd your-repo

# 创建虚拟环境（推荐 conda）
conda create -n deep-agent-env python=3.11
conda activate deep-agent-env

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 填入你的 API Key：
- `DASHSCOPE_API_KEY`：从 [阿里百炼](https://dashscope.console.aliyun.com/) 申请
- `TAVILY_API_KEY`：从 [Tavily](https://tavily.com/) 申请（每月 1000 次免费，可选）

### 3. （可选）Docker 沙箱

如果要用 Docker 沙箱模式：
1. 安装 [Docker Desktop](https://www.docker.com/products/docker-desktop/)
2. 启动 Docker Desktop
3. 拉取基础镜像：`docker pull python:3.11-slim-bookworm`
4. 在 `.env` 里设 `USE_DOCKER_SANDBOX=true`

### 4. 运行效果

<img width="1876" height="931" alt="image" src="https://github.com/user-attachments/assets/6c0dc517-abaa-441a-83fd-88ff9aca2f5b" />


### 5. 测试话术

```
👤 你: 帮我写一个关于程序员的笑话，保存到 output/joke.txt
👤 你: 帮我调研一下黄金价格，写一份报告保存到 output/gold_report.txt
```

## 两种运行模式对比

| 维度 | 非沙箱模式（`USE_DOCKER_SANDBOX=false`） | 沙箱模式（`USE_DOCKER_SANDBOX=true`） |
|------|---------------------------------------|--------------------------------------|
| 隔离性 | 靠 permissions 控制 | 容器物理隔离 |
| execute 工具 | 不可用 | 可用（能跑 shell 命令） |
| permissions | 可用（allow/deny/interrupt） | 不可用（用容器隔离替代） |
| 文件落点 | 本机 `output/` | 容器内 `/workspace/output/` |
| 适合 | 学习 permissions / 简单任务 | 学习 execute / 高风险任务 |

## 依赖清单

```
deepagents
langchain-openai
langchain-ollama          # 可选：本地模型
langgraph-checkpoint-sqlite
duckducko-search         # 可选：免费搜索替代 Tavily
docker                   # 可选：沙箱模式
python-dotenv
pydantic
```

## 学习要点

这个项目演示了 deepagents 框架的以下能力：

1. **Agent 编排**：主 Agent + 子 Agent 的委派机制
2. **Human-in-the-Loop**：`interrupt_on` + `stream()` 实现人工审批
3. **权限控制**：`FilesystemPermission` 三态路径匹配
4. **自评循环**：`RubricMiddleware` 让 Agent 自我检查质量
5. **任务管理**：`TodoListMiddleware` 让 Agent 自主分解复杂任务
6. **沙箱隔离**：自实现 `BaseSandbox` 协议，体验容器隔离
7. **持久化记忆**：SqliteSaver + 自实现 BaseStore，对话和记忆不丢
8. **模型无关性**：同一套代码，云端 qwen 和本地 Ollama 都能跑

## Web 前端

项目包含 React + TypeScript + Vite 构建的前端界面，支持对话交互、实时流式输出、审批弹窗等。

### 前端技术栈

| 模块 | 技术 |
|------|------|
| 框架 | React 19 |
| 构建工具 | Vite 6 |
| Markdown 渲染 | react-markdown |
| 通信 | WebSocket + REST |

### 启动方式

**终端 1 — 后端**（确保 Docker Desktop 在运行）：

```bash
cd c:\Users\xieheng\Documents\trae_projects\deepagent_1\my-deep-agent
conda activate deep-agent-env
python -m uvicorn api.server:app --reload --port 8000
```

**终端 2 — 前端**：

```bash
cd c:\Users\xieheng\Documents\trae_projects\deepagent_1\my-deep-agent\frontend
npm run dev
```

前端默认在 `http://localhost:5173`，后端 API 在 `http://localhost:8000`。

### 前端目录结构

```
frontend/
├── src/                # React 源码
├── index.html          # 入口 HTML
├── package.json        # 依赖配置
├── tsconfig.json       # TypeScript 配置
└── vite.config.ts      # Vite 配置
```

### 后端目录结构

```
api/
├── __init__.py
└── server.py           # FastAPI 服务（REST + WebSocket）
```

## 局限性

- 当前用 SQLite 单机存储，生产环境建议换 Postgres
- qwen3.8-max 对 `response_format` 支持不完整，已移除结构化输出
- 沙箱模式下 permissions 不可用（deepagents 已知限制）

## 注意
- 使用的模型需要有工具调用能力，否则无法达到预期效果

## License

MIT
