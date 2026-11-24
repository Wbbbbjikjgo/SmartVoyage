# SmartVoyage - 智能旅行助手

> 基于 **真实 A2A 协议 + 真实 MCP 协议 + 大模型** 的多智能体旅行规划系统

SmartVoyage 通过自然语言交互，让多个独立运行的 A2A Agent 协作完成天气、机票、火车票、酒店/景点查询与行程规划。

**本项目不包含任何 mock / 模拟数据。** 所有结果都来自真实接口：

- 天气 / 酒店 / 景点：高德开放平台
- 航班 / 火车票：阿里云 API 市场
- 行程 / 预订：本地 MySQL

如果 API Key 缺失或接口不可用，工具会返回明确的错误，而不是伪造数据。

---

## 架构

```text
Streamlit (8501)
      │ HTTP
      ▼
FastAPI 网关 / 主 Agent (8000)
  │  1. 大模型意图识别
  │  2. 发现 Agent URL（注册中心 5000，失败时回退静态配置）
  │  3. 通过标准 A2A 协议 HTTP 调用
  ▼
┌──────────┬──────────┬──────────┬──────────┬─────────────┐
│ Weather  │ Flight   │ Train    │ Hotel    │ Itinerary   │
│ 5001     │ 5002     │ 5005     │ 5003     │ 5004        │
│ LLM+工具 │ LLM+工具 │ LLM+工具 │ LLM+工具 │ LLM+工具    │
└────┬─────┴────┬─────┴────┬─────┴────┬─────┴──────┬──────┘
     │ stdio    │ stdio    │ stdio    │ stdio      │ stdio
     ▼          ▼          ▼          ▼            ▼
 weather_mcp  flight_mcp  train_mcp  hotel_mcp    db_mcp
     │          │          │          │            │
 高德天气    阿里云航班  阿里云火车票  高德POI      MySQL
```

### 三层真实协议

| 层 | 实现 | 说明 |
| --- | --- | --- |
| Agent ↔ 外部工具 | **MCP（stdio）** | `mcp_servers/*.py` 使用 `FastMCP` + `@mcp.tool()` 注册真实工具 |
| Agent ↔ 工具调用 | `core/mcp_client.py` + `core/mcp_tool_adapter.py` | 连接 MCP Server，把 MCP 工具包装成 LangChain Tool 交给大模型 |
| Agent ↔ Agent | **A2A（HTTP）** | 每个 Agent 是独立 HTTP 服务，通过 `AgentCard` 暴露 URL 与技能 |
| 主 Agent 路由 | 大模型意图识别 + 注册中心发现 | 找到对应 Agent 的 URL 后通过 A2A 调用 |
| 槽位追问 | 会话 `pending_task` + resume | 缺少必填槽位时中断提问，用户补充后自动继续原任务 |

每个 Agent 内部都有自己的大模型（DeepSeek），工具列表由 MCP 动态发现后绑定给大模型，由大模型自主决定调用哪个工具、传什么参数。

---

## 目录结构

```text
SmartVoyage/
├── agents/                  # 真正的 A2A Agents（每个子目录一个独立服务）
│   ├── base_executor.py     # LLM + MCP 工具 + A2A Artifact 返回
│   ├── server.py            # AgentCard / uvicorn / 注册
│   ├── weather/             # __main__.py(描述) + agent_executor.py(功能)
│   ├── flight/
│   ├── train/
│   ├── hotel/
│   └── itinerary/
├── mcp_servers/             # 真正的 MCP Servers（stdio + @mcp.tool）
│   ├── weather_mcp.py
│   ├── flight_mcp.py
│   ├── train_mcp.py
│   ├── hotel_mcp.py
│   └── db_mcp.py
├── core/
│   ├── mcp_client.py        # MCP stdio 客户端
│   ├── mcp_tool_adapter.py  # MCP 工具 -> LangChain Tool
│   ├── registry_client.py   # Agent 注册 + 心跳
│   ├── llm.py               # 统一 DeepSeek 客户端
│   ├── intent_recognizer.py # 主 Agent 意图识别
│   └── slot_filler.py       # 槽位提取
├── registry/server.py       # A2A 注册与发现中心
├── orchestrator/
│   ├── a2a_client.py        # 标准 A2A 客户端
│   ├── agent_directory.py   # 注册中心发现 + 静态回退
│   ├── router.py            # 意图 -> 远程 Agent URL
│   └── workflows.py         # 多 Agent 协作旅行规划
├── api/                     # FastAPI 网关
├── web/                     # Streamlit 前端
├── models/                  # SQLAlchemy + Pydantic
├── configs/settings.py      # 配置
└── scripts/start_all.py     # 一键启动全部服务
```

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

填入真实 Key：

| 变量 | 说明 |
| --- | --- |
| `OPENAI_API_KEY` | DeepSeek API Key（每个 Agent 的大模型都用它） |
| `OPENAI_BASE_URL` | 默认 `https://api.deepseek.com` |
| `OPENAI_MODEL` | 默认 `deepseek-chat` |
| `AMAP_API_KEY` | 高德 Web 服务 Key（天气 + 酒店 + 景点） |
| `ALIYUN_APPCODE` | 阿里云 API 市场 AppCode（航班 + 火车票） |
| `MYSQL_PASSWORD` | 本地 MySQL 密码 |

> 没有 Key 也能启动服务：对应 MCP 工具会返回明确的“缺少 Key / 接口失败”错误，绝不会返回假数据。

### 3. 初始化数据库（Itinerary Agent 使用）

```bash
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS smartvoyage CHARACTER SET utf8mb4;"
```

### 4. 启动全部服务

```bash
python scripts/start_all.py
```

或手动按顺序启动：

```bash
# 1) 注册中心
python -m registry.server                 # http://127.0.0.1:5000

# 2) A2A Agents（各自会自动通过 stdio 拉起对应 MCP Server）
python -m agents.weather                  # http://127.0.0.1:5001
python -m agents.flight                   # http://127.0.0.1:5002
python -m agents.hotel                    # http://127.0.0.1:5003
python -m agents.itinerary                # http://127.0.0.1:5004
python -m agents.train                    # http://127.0.0.1:5005

# 3) API 网关（主 Agent）
uvicorn api.main:app --host 0.0.0.0 --port 8000

# 4) Streamlit 前端
streamlit run web/app.py --server.port 8501
```

### 5. 访问

| 入口 | 地址 |
| --- | --- |
| 前端界面 | http://localhost:8501 |
| API 文档 | http://localhost:8000/docs |
| 注册中心 Agent 列表 | http://localhost:5000/.well-known/agents |
| 某个 Agent 的 AgentCard | http://localhost:5001/.well-known/agent-card.json |

---

## 请求流程（以“北京天气”为例）

1. Streamlit → `POST /api/chat/`
2. 主 Agent 用大模型识别意图为 `weather_query`，提取城市 `北京`
3. 主 Agent 从注册中心发现 `Weather Agent` 的 URL `http://127.0.0.1:5001`
4. 通过标准 A2A 协议发送 `Message`
5. Weather Agent 的大模型收到请求，自主选择 MCP 工具 `get_current_weather`
6. MCP Client 通过 stdio 调用 `mcp_servers.weather_mcp` 的 `@mcp.tool()`
7. MCP Server 调用真实高德天气 API 并返回 JSON
8. Weather Agent 的大模型整理成自然语言回答，作为 A2A Artifact 返回
9. 主 Agent 把结果返回给前端

行程规划会依次调用 Weather / Hotel / Flight / Train Agent，再把真实数据交给 Itinerary Agent 生成逐日计划并写入 MySQL。

---

## 测试

```bash
pytest tests/ -v
```

测试覆盖：

- MCP Server 工具确实通过 `@mcp.tool()` 注册
- 缺少 Key / 上游失败时返回明确错误（无 mock 降级）
- 航班 / 火车票真实返回结构的归一化
- 高德 POI 不伪造房价与设施
- 主 Agent 意图 → Agent/Skill → 参数映射 → 远程调用的路由逻辑

---

## 开发约定

- Python 3.11+，PEP 8，4 空格缩进
- 所有公开函数/类添加 docstring 与类型注解
- 配置统一放 `configs/settings.py`，从环境变量读取
- 日志使用 `logging`，MCP Server 的日志必须写 stderr（不能污染 stdio）
- Git 提交遵循 Conventional Commits

详见 [AGENTS.md](AGENTS.md)。
