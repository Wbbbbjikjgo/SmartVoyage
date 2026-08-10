# SmartVoyage 旅行智能助手 — 技术文档

> 基于 A2A（Agent-to-Agent）协议的多智能体旅行规划系统

| 文档信息 | 内容 |
| --- | --- |
| 项目名称 | SmartVoyage 旅行智能助手 |
| 文档版本 | v1.0 |
| 协议栈 | A2A + MCP |
| 核心技术 | python-a2a / LangChain / ChatOpenAI / FastAPI / Streamlit / MySQL |

---

## 1. 项目概述

### 1.1 项目背景

在旅行规划场景中，用户通常需要整合多种信息源——天气、航班、酒店、景点、当地交通等。传统做法是在多个 App 间反复切换，效率低且体验割裂。

随着 AI Agent 技术的发展，不同智能体之间的协作成为可能。本项目构建一个基于 **A2A（Agent-to-Agent）协议** 的旅行智能助手系统，通过多个专用 Agent 的协作，为用户提供从天气查询、票务预订到行程规划的一站式智能服务。

A2A 协议是 Agent 之间的"外交语言"——由 Google 于 2025 年 4 月推出，并于同年 6 月捐献给 Linux 基金会——实现了不同供应商、不同框架开发的 AI Agent 之间的**互相发现、沟通与协作**。

### 1.2 项目目标

| 目标 | 说明 |
| --- | --- |
| 多 Agent 协作 | 将旅行场景拆解为天气、票务、行程规划等子任务，由专用 Agent 协同完成 |
| 标准化通信 | 基于 A2A 协议实现 Agent 间的标准化交互，支持 Agent 发现与任务路由 |
| 工具调用集成 | 通过 MCP（Model Context Protocol）实现 Agent 对外部工具的统一调用 |
| 交互式体验 | 基于 Streamlit 构建用户友好的 Web 界面，支持自然语言对话式交互，AI 回复采用打字机式流式输出 |

### 1.3 核心能力清单

1. **LLM 意图识别**：自然语言输入 → 意图分类 + 槽位提取 → 任务路由。
2. **天气查询**：实时天气、未来预报、空气质量。
3. **票务查询**：机票、酒店的查询与预订流程。
4. **行程规划**：结合天气与票务结果生成完整行程。
5. **数据库读写**：用户信息、行程记录、预订记录的持久化。

---

## 2. 技术架构

### 2.1 总体架构

系统分为五层：

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                        前端交互层 (Streamlit)                                │
│  对话界面 │ 行程展示 │ 天气卡片 │ 票务结果（支持流式打字机输出）             │
├─────────────────────────────────────────────────────────────────────────────┤
│                    API 网关层 (FastAPI + Uvicorn)                            │
│            A2A Protocol Server + Agent Card (.well-known/agent-card.json)    │
├─────────────────────────────────────────────────────────────────────────────┤
│                  智能体协作层 (python-a2a + LangChain)                       │
│   意图识别 Agent │ 天气 Agent │ 票务 Agent │ 行程规划 Agent（A2A 网络）      │
├─────────────────────────────────────────────────────────────────────────────┤
│                     工具调用层 (MCP Protocol)                                │
│      天气 API │ 票务 API │ 数据库 │ 航班 API │ 酒店 API（MCP 工具）          │
├─────────────────────────────────────────────────────────────────────────────┤
│                          数据存储层                                          │
│         MySQL (用户/行程) │ Redis (会话/缓存) │ Elasticsearch (可选)          │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 A2A 与 MCP 协议协同

本项目同时使用 A2A 和 MCP 两个协议，它们解决不同层面的问题：

| 协议 | 定位 | 本项目用途 |
| --- | --- | --- |
| A2A (Agent-to-Agent) | Agent 之间的"外交语言"——让不同 Agent 互相发现、沟通、协作 | Agent 网络发现、任务路由、多 Agent 工作流编排 |
| MCP (Model Context Protocol) | AI 的"USB 接口"——统一工具调用标准 | Agent 调用天气 API、票务 API、数据库等外部工具 |

> **一句话概括**：Agent 之间通过 A2A 协议"说话"，Agent 内部通过 MCP 协议"动手"。

### 2.3 技术栈

| 层级 | 技术选型 | 用途说明 |
| --- | --- | --- |
| 前端界面 | Streamlit | 交互式 Web 界面，快速原型开发 |
| API 网关 | FastAPI + Uvicorn | RESTful API 服务，A2A 协议承载 |
| A2A 协议实现 | python-a2a (v0.5.3) | Google A2A 协议的 Python 实现，支持 AgentCard、任务管理、流式响应 |
| AI 编排框架 | LangChain | 大模型集成、Prompt 管理、工具调用链 |
| 大语言模型 | ChatOpenAI (GPT-4 / GPT-3.5) | 意图识别、自然语言理解、回答生成 |
| 工具调用协议 | MCP (Model Context Protocol) | Agent 与外部工具的统一调用接口 |
| 数据库 | MySQL Connector | 用户数据、行程记录持久化存储 |
| 缓存 | Redis（可选） | 会话管理、API 响应缓存 |
| 外部 API | 天气 API、航班 API、酒店 API | 实时数据获取 |

---

## 3. 核心功能与实现方案

### 3.1 LLM 意图识别

**功能描述**：用户通过自然语言输入旅行需求，系统识别用户意图并路由至对应的 Agent。

**实现方案**：

1. 基于 ChatOpenAI 进行意图分类，定义意图类型：
   - `weather_query`（天气查询）
   - `flight_booking`（机票预订）
   - `hotel_booking`（酒店预订）
   - `itinerary_planning`（行程规划）
   - `general_qa`（通用问答）
2. 结合 LangChain 的 `create_extraction_chain` 进行槽位提取（目的地、日期、人数、预算等）。
3. 意图识别结果传递给 A2A 路由器，决定将任务分发给哪个 Agent。

```python
# 意图识别示例
from langchain.chains import create_extraction_chain
from langchain_openai import ChatOpenAI

schema = {
    "properties": {
        "intent": {"type": "string",
                   "enum": ["weather", "flight", "hotel", "itinerary"]},
        "destination": {"type": "string"},
        "date": {"type": "string"},
        "budget": {"type": "string"}
    }
}
llm = ChatOpenAI(model="gpt-4")
chain = create_extraction_chain(llm, schema)
result = chain.run("我想下周五去北京玩三天，预算5000")
# 输出: {"intent": "itinerary", "destination": "北京",
#        "date": "下周五", "budget": "5000"}
```

**意图 → Agent 路由映射表**：

| 意图 | 目标 Agent | 端口 |
| --- | --- | --- |
| weather_query | Weather Agent | 5001 |
| flight_booking | Flight Agent | 5002 |
| hotel_booking | Hotel Agent | 5003 |
| itinerary_planning | Itinerary Agent | 5004 |
| general_qa | 网关层 LLM 直接回答 | — |

### 3.2 A2A Agent 网络构建

**功能描述**：构建包含多个专用 Agent 的 A2A 网络，每个 Agent 通过 Agent Card 发布自身能力，支持动态发现与路由。

#### 3.2.1 Agent 定义

每个 Agent 是一个独立的 A2A 服务器，通过 `@agent` 装饰器定义，并通过 `@skill` 装饰器声明技能：

```python
# weather_agent.py - 天气查询Agent
from python_a2a import A2AServer, skill, agent, run_server

@agent(
    name="Weather Agent",
    description="提供全球各地的实时天气信息和预报，支持按城市和日期查询",
    version="1.0.0"
)
class WeatherAgent(A2AServer):

    @skill(
        name="get_weather",
        description="获取指定城市的当前天气和未来预报",
        tags=["weather", "forecast"]
    )
    def get_weather(self, location: str, date: str = None):
        # 调用天气API（通过MCP工具）
        return weather_data

    @skill(
        name="get_air_quality",
        description="获取指定城市的空气质量指数",
        tags=["weather", "air quality"]
    )
    def get_air_quality(self, location: str):
        # 空气质量查询
        return aqi_data
```

#### 3.2.2 Agent Card 发布

每个 Agent 自动发布 `/.well-known/agent-card.json` 端点，描述其身份、能力和技能：

```json
{
  "name": "Weather Agent",
  "description": "提供全球各地的实时天气信息和预报",
  "version": "1.0.0",
  "url": "http://localhost:5001",
  "skills": [
    {"name": "get_weather", "description": "获取指定城市的当前天气和未来预报"},
    {"name": "get_air_quality", "description": "获取指定城市的空气质量指数"}
  ]
}
```

#### 3.2.3 Agent Network 与路由

基于 `AIAgentRouter` 实现 LLM 驱动的智能路由，根据用户问题自动选择最合适的 Agent：

```python
from python_a2a import AgentNetwork, AIAgentRouter

# 创建Agent网络
network = AgentNetwork()
network.add("weather", "http://localhost:5001")
network.add("flight", "http://localhost:5002")
network.add("hotel", "http://localhost:5003")
network.add("itinerary", "http://localhost:5004")

# 创建LLM驱动的路由器
router = AIAgentRouter(
    llm_client=network.get_agent("weather"),  # 使用一个Agent作为LLM进行路由决策
    agent_network=network
)

# 路由查询
agent_name, confidence = router.route_query("北京下周天气怎么样？")
# 输出: ("weather", 0.95)
```

**Agent 清单**：

| Agent | 职责 | 核心技能 |
| --- | --- | --- |
| Weather Agent | 天气与空气质量 | get_weather、get_air_quality |
| Flight Agent | 机票查询与预订 | search_flights、book_flight |
| Hotel Agent | 酒店查询与预订 | search_hotels、book_hotel |
| Itinerary Agent | 行程规划编排 | plan_itinerary |

### 3.3 MCP 工具调用集成

**功能描述**：Agent 通过 MCP 协议调用外部工具（天气 API、票务 API、数据库等），实现统一工具接口。

```python
# MCP工具定义示例
from python_a2a.mcp import FastMCP, text_response

# 创建天气工具MCP服务器
weather_mcp = FastMCP(name="Weather Tools", description="天气查询工具集")

@weather_mcp.tool(
    name="get_current_weather",
    description="获取城市当前天气"
)
def get_current_weather(location: str) -> str:
    # 调用外部天气API
    response = requests.get(f"https://api.weather.com/current?city={location}")
    return text_response(response.json())

# 启动MCP服务器
weather_mcp.run(port=5010)

# Agent通过MCP客户端调用工具
from python_a2a.mcp import MCPClient

mcp_client = MCPClient("http://localhost:5010")
weather_data = mcp_client.call_tool("get_current_weather", {"location": "北京"})
```

**MCP 服务器与端口规划**：

| MCP 服务器 | 端口 | 提供的工具 |
| --- | --- | --- |
| weather_mcp | 5010 | get_current_weather、get_forecast、get_air_quality |
| flight_mcp | 5011 | search_flights、get_flight_detail |
| hotel_mcp | 5012 | search_hotels、get_hotel_detail |
| db_mcp | 5013 | query_user、save_itinerary、save_booking、list_bookings |

### 3.4 多 Agent 工作流编排

**功能描述**：基于 A2A 的 Flow 机制，定义包含条件分支和并行执行的多 Agent 工作流，完成复杂的旅行规划任务。

```python
from python_a2a import Flow

# 创建旅行规划工作流
workflow = Flow(
    agent_network=network,
    router=router,
    name="Travel Planning Workflow"
)

# 第一步：获取天气
workflow.ask("weather", "What's the weather in {destination} on {date}?")

# 根据天气条件分支
workflow.if_contains("sunny")
    # 晴天推荐户外活动
    workflow.ask("itinerary", "Recommend outdoor activities in {destination}")
workflow.else_branch()
    # 阴雨推荐室内活动
    workflow.ask("itinerary", "Recommend indoor activities in {destination}")
workflow.end_if()

# 并行执行票务查询
workflow.ask("flight", "Find flights to {destination} for {date}")
workflow.ask("hotel", "Find hotels in {destination} for {duration} nights")

# 执行工作流
result = await workflow.run({
    "destination": "北京",
    "date": "2026-08-15",
    "duration": 3
})
```

**工作流执行序列**：

```text
用户请求(行程规划)
    │
    ▼
[1] Weather Agent: 查询目的地天气 ──┐
    │                               │ 条件分支
    ├─ 晴天 → 推荐户外活动           │
    └─ 阴雨 → 推荐室内活动           │
    ▼
[2] Flight Agent ─┐
[3] Hotel Agent  ─┴─ 并行查询票务
    ▼
[4] Itinerary Agent: 汇总生成完整行程
    ▼
[5] db_mcp: 行程落库保存
```

### 3.5 数据库查询与存储

**功能描述**：使用 MySQL 存储用户信息、行程记录、历史查询等数据。

**实现方案**：

- 使用 MySQL Connector 连接数据库；
- 通过 MCP 工具（db_mcp）封装数据库操作，供 Agent 调用；
- 核心表：`users`、`itineraries`、`bookings`。

**建表 DDL**：

```sql
CREATE TABLE users (
    user_id     BIGINT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(64)  NOT NULL,
    email       VARCHAR(128) NOT NULL UNIQUE,
    preferences JSON,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE itineraries (
    itinerary_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id      BIGINT NOT NULL,
    destination  VARCHAR(64) NOT NULL,
    start_date   DATE NOT NULL,
    duration     INT NOT NULL,
    budget       DECIMAL(12,2),
    status       VARCHAR(16) DEFAULT 'draft',  -- draft/confirmed/cancelled
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE bookings (
    booking_id   BIGINT AUTO_INCREMENT PRIMARY KEY,
    itinerary_id BIGINT NOT NULL,
    type         VARCHAR(16) NOT NULL,   -- flight/hotel/ticket
    details      JSON,
    status       VARCHAR(16) DEFAULT 'pending',  -- pending/paid/cancelled
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (itinerary_id) REFERENCES itineraries(itinerary_id)
);
```

### 3.6 Streamlit 前端界面

**功能描述**：提供交互式 Web 界面，用户通过聊天方式输入旅行需求，实时查看 Agent 处理结果。

**实现方案**：

- 基于 Streamlit 构建对话式 UI；
- 集成 `st.chat_input` 实现消息输入；
- 通过 FastAPI 后端调用 A2A Agent 网络；
- 支持流式响应，AI 回复以**打字机效果逐字输出**（`st.write_stream`），实时展示 Agent 处理过程；
- 展示天气卡片、航班列表、行程规划等富文本内容。

---

## 4. 数据库设计

### 4.1 ER 图

```text
┌─────────────┐         ┌──────────────────┐         ┌─────────────┐
│   users     │         │   itineraries    │         │  bookings   │
├─────────────┤         ├──────────────────┤         ├─────────────┤
│ user_id(PK) │◄────────│ itinerary_id(PK) │         │ booking_id  │
│ name        │         │ user_id(FK)      │◄────────│ itinerary_id│
│ email       │         │ destination      │         │ type        │
│ preferences │         │ start_date       │         │ details     │
│ created_at  │         │ duration         │         │ status      │
└─────────────┘         │ budget           │         │ created_at  │
                        │ status           │         └─────────────┘
                        │ created_at       │
                        │ updated_at       │
                        └──────────────────┘
```

### 4.2 字段说明

| 表 | 字段 | 类型 | 说明 |
| --- | --- | --- | --- |
| users | user_id | BIGINT PK | 用户主键 |
| users | preferences | JSON | 用户偏好（舱位、酒店星级等） |
| itineraries | duration | INT | 行程天数 |
| itineraries | status | VARCHAR(16) | draft / confirmed / cancelled |
| bookings | type | VARCHAR(16) | flight / hotel / ticket |
| bookings | details | JSON | 预订明细（航班号、房型等） |

---

## 5. 项目结构

```text
smartvoyage/
├── agents/                             # A2A智能体
│   ├── __init__.py
│   ├── base_agent.py                   # 基础Agent类
│   ├── weather_agent.py                # 天气查询Agent (A2A服务)
│   ├── flight_agent.py                 # 机票查询Agent (A2A服务)
│   ├── hotel_agent.py                  # 酒店查询Agent (A2A服务)
│   └── itinerary_agent.py              # 行程规划Agent (A2A服务)
├── mcp_servers/                        # MCP工具服务器
│   ├── __init__.py
│   ├── weather_mcp.py                  # 天气API工具
│   ├── flight_mcp.py                   # 航班API工具
│   ├── hotel_mcp.py                    # 酒店API工具
│   └── db_mcp.py                       # 数据库操作工具
├── orchestrator/                       # 工作流编排
│   ├── __init__.py
│   ├── router.py                       # A2A路由器
│   ├── workflows.py                    # Flow工作流定义
│   └── agent_network.py                # Agent网络管理
├── core/                               # 核心模块
│   ├── __init__.py
│   ├── intent_recognizer.py            # LLM意图识别
│   ├── slot_filler.py                  # 槽位填充
│   └── context_manager.py              # 上下文管理
├── api/                                # API层
│   ├── __init__.py
│   ├── main.py                         # FastAPI主程序
│   ├── routes/
│   │   ├── chat.py                     # 对话接口
│   │   └── agent.py                    # A2A协议端点
│   └── dependencies.py
├── web/                                # Streamlit前端
│   ├── app.py                          # 主界面
│   ├── pages/
│   │   ├── chat.py
│   │   ├── itinerary.py
│   │   └── settings.py
│   └── components/
├── models/                             # 数据模型
│   ├── __init__.py
│   ├── schemas.py                      # Pydantic模型
│   └── database.py                     # SQLAlchemy/MySQL模型
├── configs/                            # 配置文件
│   ├── __init__.py
│   ├── settings.py
│   └── .env.example
├── deploy/                             # 部署配置
│   ├── docker-compose.yml
│   └── Dockerfile
├── tests/                              # 测试
│   ├── test_agents.py
│   └── test_workflows.py
├── requirements.txt
├── Makefile
└── README.md
```

---

## 6. 接口设计

### 6.1 API 网关层接口（FastAPI）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/.well-known/agent-card.json` | 网关 Agent Card（能力总览） |
| POST | `/api/chat` | 对话接口，入参 `{message, session_id}`，支持 SSE 流式返回 |
| GET | `/api/agents` | 列出已注册的 Agent 网络 |
| POST | `/api/itineraries` | 保存行程 |
| GET | `/api/itineraries/{user_id}` | 查询用户行程列表 |

### 6.2 A2A 端点（每个 Agent）

| 路径 | 说明 |
| --- | --- |
| `/.well-known/agent-card.json` | Agent Card，供网络发现 |
| `/a2a/tasks/send` | 提交任务 |
| `/a2a/tasks/{id}/status` | 查询任务状态 |
| `/a2a/tasks/send-subscribe` | 流式任务（SSE），驱动前端打字机效果 |

### 6.3 MCP 工具调用约定

Agent 通过 `MCPClient.call_tool(tool_name, arguments)` 调用工具，返回值统一为 `text_response(json)` 格式；工具内部异常需转换为结构化错误 JSON：

```json
{"error": true, "code": "UPSTREAM_TIMEOUT", "message": "天气API超时"}
```

---

## 7. 运行与部署

### 7.1 端口规划总览

| 服务 | 端口 |
| --- | --- |
| API 网关 (FastAPI/Uvicorn) | 8000 |
| Weather Agent | 5001 |
| Flight Agent | 5002 |
| Hotel Agent | 5003 |
| Itinerary Agent | 5004 |
| weather_mcp | 5010 |
| flight_mcp | 5011 |
| hotel_mcp | 5012 |
| db_mcp | 5013 |
| Streamlit 前端 | 8501 |
| MySQL | 3306 |
| Redis（可选） | 6379 |

### 7.2 启动顺序

1. 启动 MySQL / Redis（基础设施）；
2. 启动 4 个 MCP 工具服务器（5010–5013）；
3. 启动 4 个 A2A Agent（5001–5004）；
4. 启动 FastAPI 网关（8000）；
5. 启动 Streamlit 前端（8501）。

### 7.3 环境变量（.env）

```env
OPENAI_API_KEY=sk-xxxx
OPENAI_MODEL=gpt-4
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=xxxx
MYSQL_DATABASE=smartvoyage
REDIS_URL=redis://localhost:6379/0
WEATHER_API_KEY=xxxx
```

### 7.4 Docker Compose（生产部署）

通过 `deploy/docker-compose.yml` 编排全部服务，各 Agent 与 MCP 服务器独立容器化，网关统一对外暴露 8000 端口。

---

## 8. 测试策略

| 层级 | 测试内容 | 工具 |
| --- | --- | --- |
| Agent 层 | 各 Agent 技能单测、Agent Card 正确性 | pytest |
| 路由层 | 意图识别准确率、路由命中率 | pytest + 用例集 |
| 工作流层 | Flow 条件分支、并行执行结果 | pytest-asyncio |
| 集成层 | 端到端对话链路（前端 → 网关 → Agent → MCP → DB） | pytest + httpx |

---

## 9. 附录：术语表

| 术语 | 说明 |
| --- | --- |
| A2A | Agent-to-Agent，Google 推出并捐献 Linux 基金会的智能体互操作协议 |
| MCP | Model Context Protocol，AI 模型与外部工具的统一调用标准 |
| Agent Card | A2A 中 Agent 的自描述文件，位于 `/.well-known/agent-card.json` |
| Skill | Agent 对外声明的一项可调用能力 |
| Flow | python-a2a 提供的多 Agent 工作流编排机制，支持条件分支与并行 |
| 槽位提取 | 从用户自然语言中抽取结构化参数（目的地、日期、预算等） |
