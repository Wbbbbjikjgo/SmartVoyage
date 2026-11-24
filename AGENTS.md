# SmartVoyage AI Agent 开发指南

> 本文档供 AI 助手（及人类开发者）参考，确保开发过程规范、高效、不跑偏。

---

## 1. 项目概述

**SmartVoyage** 是一个基于 A2A（Agent-to-Agent）协议的多智能体旅行规划系统。

**核心能力**：
- 用户通过自然语言输入旅行需求
- 系统识别意图并路由至对应 Agent
- 多个 Agent 协作完成天气查询、票务查询、行程规划
- 前端以打字机效果流式展示 AI 回复

---

## 2. 技术栈

| 层级 | 技术 | 说明 |
| --- | --- | --- |
| 前端 | Streamlit | 对话式 UI，展示 Agent 真实回答 |
| API 网关 | FastAPI + Uvicorn | RESTful 入口 + 主 Agent 意图识别 |
| A2A 协议 | `a2a-sdk==0.3.0` | 每个 Agent 是独立 A2A HTTP 服务（AgentCard + JSON-RPC） |
| AI 编排 | LangChain + LangGraph | 每个 Agent 用 `create_agent` 自主调用工具 |
| LLM | DeepSeek（兼容 OpenAI 格式） | 主 Agent 意图识别 + 各 Agent 自主决策 |
| 工具调用 | MCP（FastMCP / stdio） | `@mcp.tool()` 注册真实工具 + MCP Client/Adapter |
| 服务发现 | 自建 Registry（5000） | Agent 注册/心跳，主 Agent 按名称发现 URL |
| 数据库 | MySQL 8.0（本地） | 持久化存储 |
| 缓存 | Redis（本地） | 会话管理 |
| 日志 | Elasticsearch（Docker） | 可选，日志分析 |

---

## 3. 开发规范

### 3.1 代码风格

- **Python 版本**：3.11+
- **代码格式**：遵循 PEP 8，使用 4 空格缩进
- **命名规范**：
  - 类名：PascalCase（如 `WeatherAgent`）
  - 函数/变量：snake_case（如 `get_weather`）
  - 常量：UPPER_SNAKE_CASE（如 `OPENAI_API_KEY`）
- **类型注解**：所有函数参数和返回值必须添加类型注解
- **文档字符串**：所有公开函数/类必须添加 docstring

### 3.2 模块职责

| 模块 | 职责 | 边界 |
| --- | --- | --- |
| `agents/` | 独立 A2A Agent 服务（weather/flight/train/hotel/itinerary） | 每个 Agent 拥有自己的大模型；工具必须通过 MCP 获取 |
| `mcp_servers/` | 真正的 MCP Server（FastMCP + `@mcp.tool()`，stdio） | 只封装真实外部 API / MySQL，禁止任何 mock 数据 |
| `orchestrator/` | 主 Agent 编排 | 发现远程 Agent URL 并通过 A2A 协议调用，不做进程内直接调用 |
| `registry/` | A2A 注册与发现中心 | Agent 启动注册 + 心跳，暴露 `/.well-known/agents` |
| `core/` | 核心逻辑 | MCP Client/Adapter、意图识别、槽位填充、上下文 |
| `api/` | API 网关 | FastAPI 路由，调用主 Agent 路由与远程 A2A Agent |
| `web/` | 前端 | Streamlit UI，调用 API 网关 |
| `models/` | 数据模型 | Pydantic Schema + SQLAlchemy 模型 |
| `configs/` | 配置管理 | 环境变量加载、配置类 |

### 3.3 依赖与调用方向

```text
web/ → api/ → orchestrator/ ──(A2A HTTP)──→ agents/<name>/ ──(MCP stdio)──→ mcp_servers/
                  │                              │
                  └──────────→ registry/ ←───────┘（注册与发现）
                  ↓
                core/  （MCP client / intent / slots）
                  ↓
               models/ → configs/
```

**关键约束**：

- Agent 之间只能通过 A2A HTTP URL 通信，禁止在 orchestrator 中 `import` 并直接调用 Agent 类。
- Agent 只能通过 MCP Client 调用工具，禁止在 Agent 中直接调用外部 API。
- MCP Server 必须用 `@mcp.tool()` 注册工具，禁止只返回一个手写的工具列表。
- 槽位必填规则统一放 `core/slot_filler.py`；缺失时 router 必须中断追问并保存 `pending_task`，用户补充后 resume，禁止直接丢弃请求。
- 任何外部接口失败都必须返回明确错误，禁止伪造/模拟数据。

---

## 4. Git 提交规范

### 4.1 Conventional Commits

每个功能/修复必须使用以下格式提交：

```text
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### 4.2 Type 类型

| Type | 说明 | 示例 |
| --- | --- | --- |
| `feat` | 新功能 | `feat(weather-agent): add get_weather skill` |
| `fix` | 修复 Bug | `fix(router): correct intent mapping` |
| `docs` | 文档变更 | `docs: update AGENTS.md with commit convention` |
| `style` | 代码格式（不影响逻辑） | `style: format code with black` |
| `refactor` | 重构（非新功能、非修复） | `refactor(db): extract base agent class` |
| `test` | 测试相关 | `test: add unit tests for intent recognizer` |
| `chore` | 构建/工具/依赖变更 | `chore: add requirements.txt` |
| `perf` | 性能优化 | `perf: cache weather API responses` |
| `ci` | CI/CD 变更 | `ci: add GitHub Actions workflow` |

### 4.3 Scope 范围

常用 scope：
- `config`：配置相关
- `model`：数据模型
- `mcp`：MCP 工具服务器
- `agent`：A2A Agent
- `orchestrator`：工作流编排
- `core`：核心模块（意图识别等）
- `api`：API 网关
- `web`：前端
- `db`：数据库相关

### 4.4 提交节奏

**每完成一个独立功能点，立即提交**，不要堆积。

示例提交序列：
```bash
git commit -m "chore(config): add requirements.txt and .env.example"
git commit -m "feat(model): add Pydantic schemas for user/itinerary/booking"
git commit -m "feat(db): create MySQL tables with SQLAlchemy"
git commit -m "feat(mcp): implement real weather MCP server with FastMCP and AMap"
git commit -m "feat(mcp): implement real flight MCP server with Aliyun API"
git commit -m "feat(mcp): implement real hotel MCP server with AMap POI"
git commit -m "feat(mcp): implement database MCP server"
git commit -m "feat(agent): implement base A2A agent class"
git commit -m "feat(agent): implement weather agent with skills"
git commit -m "feat(agent): implement flight agent"
git commit -m "feat(agent): implement hotel agent"
git commit -m "feat(agent): implement itinerary agent"
git commit -m "feat(core): implement intent recognizer with DeepSeek"
git commit -m "feat(core): implement slot filler"
git commit -m "feat(core): implement context manager"
git commit -m "feat(orchestrator): implement agent network and router"
git commit -m "feat(orchestrator): implement travel planning workflow"
git commit -m "feat(api): implement FastAPI gateway with A2A endpoints"
git commit -m "feat(web): implement Streamlit chat UI with streaming"
git commit -m "test: add end-to-end integration tests"
```

---

## 5. 环境与配置

### 5.1 API Keys

| Key | 用途 | 来源 |
| --- | --- | --- |
| `OPENAI_API_KEY` | DeepSeek LLM | DeepSeek 开放平台 |
| `OPENAI_BASE_URL` | DeepSeek API 地址 | `https://api.deepseek.com` |
| `OPENAI_MODEL` | 模型名 | `deepseek-chat` |
| `AMAP_API_KEY` | 天气查询 + 酒店搜索 + 地理编码 | 高德开放平台 |
| `ALIYUN_APPCODE` | 航班查询 + 火车票查询 | 阿里云 API 市场 |
| `MYSQL_*` | 本地 MySQL | 本地安装 |
| `REDIS_URL` | 本地 Redis | 本地安装 |

> 项目已彻底移除 mock 开关。航班/火车票为付费接口，请自行控制调用频率；缺少 Key 或额度用尽时工具会返回明确错误，不会返回假数据。

### 5.2 端口规划

| 服务 | 端口 | 说明 |
| --- | --- | --- |
| A2A 注册中心 | 5000 | Agent 注册与发现 |
| Weather Agent | 5001 | A2A HTTP 服务 |
| Flight Agent | 5002 | A2A HTTP 服务 |
| Hotel Agent | 5003 | A2A HTTP 服务 |
| Itinerary Agent | 5004 | A2A HTTP 服务 |
| Train Agent | 5005 | A2A HTTP 服务 |
| FastAPI 网关 | 8000 | API 入口（主 Agent） |
| Streamlit | 8501 | 前端 |
| MCP Servers | 无端口 | 由各自 Agent 以 stdio 子进程启动 |
| MySQL | 3306 | 本地 |
| Redis | 6379 | 本地 |
| ES | 9200 | Docker |

### 5.3 启动顺序

1. MySQL（Itinerary Agent 的 db MCP 需要）
2. A2A 注册中心（5000）
3. A2A Agents（5001–5005；每个 Agent 会在首次请求时通过 stdio 拉起自己的 MCP Server）
4. FastAPI 网关（8000）
5. Streamlit 前端（8501）

也提供一键启动：`python scripts/start_all.py`

---

## 6. 防呆指南（Token 节省 & 避免跑偏）

### 6.1 不要做的事

- ❌ 不要一次性生成所有代码，按模块逐步实现
- ❌ 不要修改已稳定的接口，除非有明确需求
- ❌ 不要引入文档中未提及的第三方库
- ❌ 不要在 Agent 中直接调用外部 API，必须通过 MCP 工具
- ❌ 不要返回 mock / 伪造数据；失败就返回明确错误
- ❌ 不要硬编码 API Key，必须从环境变量读取
- ❌ 不要跳过测试，每个模块必须有基本验证

### 6.2 必须做的事

- ✅ 每个模块完成后立即 git commit
- ✅ 使用类型注解和 docstring
- ✅ 配置项统一放 `configs/settings.py`
- ✅ 错误处理要统一，不要吞异常
- ✅ 日志使用 `logging` 模块，不要用 `print`

### 6.3 Token 节省技巧

- 修改文件时，只输出变更部分，不要重复整个文件
- 使用 `SearchReplace` 而非 `Write` 修改已有文件
- 批量查询用并行工具调用，不要串行
- 遇到不确定的 API，先查文档，不要猜测

---

## 7. 测试策略

| 层级 | 测试内容 | 工具 |
| --- | --- | --- |
| 单元测试 | 各模块核心函数 | pytest |
| 集成测试 | Agent → MCP → 外部 API | pytest + httpx |
| 端到端测试 | 前端 → 网关 → Agent → 数据库 | 手动 + 自动化 |

**测试命令**：
```bash
pytest tests/ -v
```

---

## 8. 常见问题

### Q1: A2A 用哪个库？

**A**: 使用官方 `a2a-sdk==0.3.0`。每个 Agent 的 `__main__.py` 通过 `A2AStarletteApplication` 暴露标准 AgentCard 与 JSON-RPC HTTP 接口；客户端使用 `A2ACardResolver` + `A2AClient` 按 URL 调用。不要再用自建“伪 A2A”（直接 Python 调用 Agent 类）。

### Q2: DeepSeek 返回格式与 OpenAI 不同？

**A**: DeepSeek 兼容 OpenAI 格式，使用 `langchain_openai.ChatOpenAI` 时设置 `base_url` 即可。

### Q3: 高德天气 API 返回结构？

**A**: 参考官方文档 https://lbs.amap.com/api/webservice/guide/api/weatherinfo，主要参数：
- `city`：adcode（行政区划编码），项目已内置城市→adcode 映射
- `extensions=base`：实况天气（返回 `lives`）
- `extensions=all`：天气预报（返回 `forecasts[].casts`，最多 4 天）

---

## 9. 检查清单（开发前必读）

- [ ] 已阅读本 AGENTS.md
- [ ] 了解项目技术栈和架构
- [ ] 熟悉 Git 提交规范
- [ ] 知道各模块职责和边界
- [ ] 了解 API Key 和端口配置
- [ ] 知道启动顺序和测试方法

**开始开发前，请确认以上全部打勾。**
