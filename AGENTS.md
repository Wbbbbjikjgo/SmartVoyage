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
| 前端 | Streamlit | 对话式 UI，支持流式输出 |
| API 网关 | FastAPI + Uvicorn | RESTful + A2A 协议承载 |
| A2A 协议 | python-a2a | Agent 发现、通信、工作流 |
| AI 编排 | LangChain | LLM 集成、工具调用 |
| LLM | DeepSeek（兼容 OpenAI 格式） | 意图识别、回答生成 |
| 工具调用 | MCP | Agent 调用外部工具 |
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
| `agents/` | A2A Agent 实现 | 只负责 Agent 技能定义，不直接调用外部 API |
| `mcp_servers/` | MCP 工具服务器 | 封装外部 API 调用，对 Agent 提供统一工具接口 |
| `orchestrator/` | 工作流编排 | 管理 Agent 网络、路由、Flow 执行 |
| `core/` | 核心逻辑 | 意图识别、槽位填充、上下文管理 |
| `api/` | API 网关 | FastAPI 路由、A2A 端点暴露 |
| `web/` | 前端 | Streamlit UI，调用 API 网关 |
| `models/` | 数据模型 | Pydantic Schema + SQLAlchemy 模型 |
| `configs/` | 配置管理 | 环境变量加载、配置类 |

### 3.3 依赖方向

```text
web/ → api/ → orchestrator/ → agents/ → mcp_servers/
                  ↓
                core/
                  ↓
               models/
                  ↓
              configs/
```

**禁止反向依赖**：下层模块不得 import 上层模块。

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
git commit -m "feat(mcp): implement weather MCP server with QWeather API"
git commit -m "feat(mcp): implement mock flight MCP server"
git commit -m "feat(mcp): implement mock hotel MCP server"
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

> 航班/火车票为付费接口，免费额度极少，默认 `FLIGHT_MOCK_MODE` / `TRAIN_MOCK_MODE` 为 `true` 保护额度。

### 5.2 端口规划

| 服务 | 端口 | 说明 |
| --- | --- | --- |
| FastAPI 网关 | 8000 | API 入口 |
| Weather Agent | 5001 | A2A 服务 |
| Flight Agent | 5002 | A2A 服务 |
| Train Agent | 5005 | A2A 服务 |
| Hotel Agent | 5003 | A2A 服务 |
| Itinerary Agent | 5004 | A2A 服务 |
| weather_mcp | 5010 | MCP 工具 |
| flight_mcp | 5011 | MCP 工具 |
| hotel_mcp | 5012 | MCP 工具 |
| db_mcp | 5013 | MCP 工具 |
| train_mcp | 5014 | MCP 工具 |
| Streamlit | 8501 | 前端 |
| MySQL | 3306 | 本地 |
| Redis | 6379 | 本地 |
| ES | 9200 | Docker |

### 5.3 启动顺序

1. MySQL / Redis / ES（基础设施）
2. MCP 工具服务器（5010–5013）
3. A2A Agent（5001–5004）
4. FastAPI 网关（8000）
5. Streamlit 前端（8501）

---

## 6. 防呆指南（Token 节省 & 避免跑偏）

### 6.1 不要做的事

- ❌ 不要一次性生成所有代码，按模块逐步实现
- ❌ 不要修改已稳定的接口，除非有明确需求
- ❌ 不要引入文档中未提及的第三方库
- ❌ 不要在 Agent 中直接调用外部 API，必须通过 MCP 工具
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

### Q1: python-a2a 库不存在？

**A**: `python-a2a` 是社区实现，可能版本不稳定。若不可用，可退化为自建 A2A 协议实现（基于 FastAPI 的 HTTP 调用 + Agent Card JSON）。

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
