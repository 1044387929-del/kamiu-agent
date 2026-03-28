# Kamiu Agent

> 教师智能助手：基于 LangGraph + FastAPI 的对话 Agent，与 Django 解耦，支持多轮对话、工具调用与思考模式（规划：查数、学科知识）。

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-009688?style=flat-square&logo=fastapi&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-Agent-1C3C3C?style=flat-square&logo=langchain&logoColor=white)
![Pydantic](https://img.shields.io/badge/Pydantic-Settings-E6526F?style=flat-square&logo=pydantic&logoColor=white)
![Uvicorn](https://img.shields.io/badge/Uvicorn-ASGI-499848?style=flat-square&logo=uvicorn&logoColor=white)

---

## ✨ 特性

- **LangGraph 编排**：路由 → Schema Linking（相关表结构筛选）→ Agent（LLM + 动态工具绑定）→ 条件边（有 tool_calls 则执行工具再回到 Agent）
- **双模式接口**：非流式 `POST /api/chat`、流式 SSE `POST /api/chat/stream`，同一图逻辑
- **思考模式**：可选 `enable_thinking`，兼容支持推理链的模型（如 deepseek-v3.2）
- **Text2SQL（只读）**：自动路由识别查库问题，先 schema linking 再生成 SQL 并只读执行（严禁写库）
- **自动修复重试**：SQL 执行失败时自动修复并重试（最多 3 次），前端可查看每次执行语句与结果
- **前端体验**：回复/思考过程支持 Markdown 渲染；执行 SQL 会单独展示“查询语句 + 运行结果”
- **开箱即用**：内置测试前端（多轮对话）、健康检查、CORS，配置从 `config/*.env` 加载

---

## 🏗 架构概览

### 请求到图的流程

前端/API 请求携带 `message`、`model`（可选）、`enable_web_search`、`enable_thinking`。服务端校验 `model`，将参数注入 state 后执行图（是否查库由路由自动判定）。

```mermaid
flowchart LR
    subgraph 请求
        A[请求: message, model, enable_web_search, enable_thinking]
    end
    subgraph 服务端
        B[校验 model / 默认]
        C["get_graph(enable_web_search)"]
        D[注入 state 执行图]
    end
    A --> B
    B --> C
    C --> D
```

### 图内执行流程

对话图由 `graph/graph.py` 定义：先走路由，若需要查库则先做 schema linking（筛选相关表结构），再进 agent；若 LLM 返回 `tool_calls` 则执行工具并回到 agent（可多轮），否则结束。

```mermaid
flowchart LR
    START([START]) --> route[route\n规则 + LLM(JSON) 路由]
    route --> need_db{enable_db_query?}
    need_db -->|是| schema_link[schema_link\n两阶段: top-k 候选 + LLM 精筛]
    need_db -->|否| agent[agent]
    schema_link --> agent[agent]
    agent --> has_tool_calls{最后一条消息\n有 tool_calls?}
    has_tool_calls -->|是| tools[tools]
    has_tool_calls -->|否| END([END])
    tools --> agent
```

| 节点 | 说明 |
|------|------|
| **route** | 意图路由：规则 + LLM(JSON) 输出，判定是否需要查库（`enable_db_query/force_db_query`） |
| **schema_link** | Schema Linking：从全量表结构中筛选“与问题最相关”的表/字段摘要（先 lexical top-k，再 LLM 精筛），写入 `schema_link` |
| **agent** | 使用本次请求所选 **model** 调用 LLM；按 state 动态绑定工具（仅暴露需要的工具）；当 `force_db_query=true` 时强制查库验证，禁止口头推断；思考模式下可返回 reasoning |
| **tools** | 执行工具调用：`get_current_time` / `get_db_schema` / `execute_readonly_sql` / `repair_sql` / `web_search`；SQL 失败会自动修复重试（最多 3 次），并通过 SSE 推送 `exec/exec_result` 给前端展示 |

---

## 📁 项目结构

```
kamiu_agent/
├── app.py                 # FastAPI 入口
├── run.sh                 # 启动脚本（默认端口 8002）
├── requirements.txt
├── config/                # 环境配置
│   ├── llm.env           # 大模型（DASHSCOPE_API_KEY、LLM_MODEL 等）
│   └── database.env      # 数据库（预留）
├── core/                  # 核心逻辑
│   ├── config.py         # 配置加载（pydantic-settings）
│   ├── agent.py          # Agent 调用封装
│   ├── deps.py           # 依赖注入
│   ├── llm/              # LLM 客户端与 Chat
│   └── schemas/          # 请求/响应模型
├── graph/                 # LangGraph 图
│   ├── state.py          # 图状态
│   ├── intent_router.py  # LLM 意图路由（JSON 输出）
│   ├── schema_link.py    # Schema Linking（两阶段筛选相关表结构）
│   ├── nodes.py          # 节点实现（route、agent）
│   └── graph.py          # 图构建与编译
├── routers/               # API 路由
│   ├── health.py         # GET /health
│   └── assistant/        # /api/chat、/api/chat/stream
├── tools/                 # 工具（如 get_current_time）
├── prompts/               # 提示词
├── docs/                  # 文档
│   └── api.md            # API 详细说明
├── scripts/               # 示例与测试
│   ├── examples/         # 如 chat_qwen_think.py
│   └── test/             # API 测试
├── static/                # 测试前端
│   └── index.html        # 多轮对话页
└── utils/
```

---

## 🚀 快速开始

### 环境要求

- Python 3.10+
- 可选：阿里云 DashScope API Key（用于 qwen 等模型）

### 安装与运行

```bash
# 克隆后进入项目目录
cd kamiu_agent

# 安装依赖
pip install -r requirements.txt

# 配置：在 config/llm.env 中设置（示例）
# DASHSCOPE_API_KEY=sk-xxx
# LLM_MODEL=qwen-plus
# ENABLE_THINKING_DEFAULT=false

# 启动服务（默认 http://0.0.0.0:8002）
./run.sh
# 或
uvicorn app:app --host 0.0.0.0 --port 8002 --reload
```

### 验证

| 用途 | 方式 |
|------|------|
| 健康检查 | `GET http://localhost:8002/health` |
| 多轮对话测试 | 浏览器打开 `http://localhost:8002/` 或 `http://localhost:8002/static/index.html` |
| 非流式对话 | `POST http://localhost:8002/api/chat`，body: `{"message": "你好", "history": []}` |
| 流式对话 | `POST http://localhost:8002/api/chat/stream`，同上 body，SSE 事件：`reasoning` \| `content` \| `exec` \| `exec_result` \| `done` |

API 请求/响应字段详见 [docs/api.md](docs/api.md)。

---

## ⚙️ 配置说明

配置来自 `config/*.env`，由 `core/config.py` 中的 `Settings` 加载：

| 变量 | 说明 | 默认 |
|------|------|------|
| `DASHSCOPE_API_KEY` | 阿里云 DashScope API Key | 必填（qwen 等） |
| `LLM_MODEL` | 模型名称 | `qwen-plus` |
| `ENABLE_THINKING_DEFAULT` | 默认是否开启思考模式 | `false` |
| `DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME` | MySQL 连接（只读 SQL） | 见 `config/database.env` |

### 数据库安全说明（重要）

- 代码层面：`execute_readonly_sql` 强制只读（仅允许 `SELECT/SHOW/DESCRIBE/EXPLAIN`），禁止多语句与危险关键字/函数，并对 `SELECT` 默认加 `LIMIT` 防止拖库。
- 建议再加一层：使用数据库 **只读账号**（仅授予 SELECT 等权限），形成双保险。

---

## 🤝 参与贡献

1. Fork 本仓库  
2. 新建功能分支（如 `feat/xxx`）  
3. 提交代码并推送到分支  
4. 提交 Pull Request  

---

## 📄 许可

按项目根目录许可文件为准。
