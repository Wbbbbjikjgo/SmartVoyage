# -*- coding: utf-8 -*-
"""Regenerate docs/从0到1源码阅读指南.md from the current source tree.

Usage: python scripts/gen_reading_guide.py
"""
import io
import os
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "从0到1源码阅读指南.md")


def read(path):
    with io.open(os.path.join(ROOT, path), "r", encoding="utf-8") as f:
        return f.read()


def code_block(path, lang="python"):
    return f"```{lang}\n{read(path).rstrip()}\n```\n"


S = []  # sections: (title, [prose...], [code blocks...])


def section(title, prose, blocks):
    S.append((title, prose, blocks))


# ================================================================
# 第 0 步
# ================================================================
section(
    "# SmartVoyage 从 0 到 1 源码阅读指南",
    [
        "> 本文档带你从零开始读懂 SmartVoyage 的每一行代码，按「依赖方向」组织章节："
        "`configs → models → mcp_servers → agents → core → orchestrator → api → web`。",
        "",
        f"> 文档自动生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}（源码与注释实时同步）。",
        "",
        "## 这个项目是干什么的",
        "",
        "SmartVoyage 是一个基于 A2A（Agent-to-Agent）协议的多智能体旅行规划系统：",
        "- 用户用自然语言描述出行需求（查天气 / 订机票 / 查高铁 / 订酒店 / 规划行程）",
        "- 系统用 DeepSeek 大模型做**意图识别**，用正则做**槽位填充**",
        "- 根据意图把任务**路由**到对应的 Agent，Agent 通过 **MCP 工具服务器**调用外部 API",
        "- 最终把结果以对话形式返回给 Streamlit 前端",
        "",
        "### 数据源（本次改造重点）",
        "",
        "| 能力 | 数据源 | 接口 |",
        "| --- | --- | --- |",
        "| 天气 | 高德开放平台 | `restapi.amap.com/v3/weather/weatherInfo` |",
        "| 酒店 | 高德开放平台 | `restapi.amap.com/v3/place/text`（关键字搜索） |",
        "| 航班 | 阿里云 API 市场 | `flightss.market.alicloudapi.com/flight/query` |",
        "| 高铁/火车票 | 阿里云 API 市场 | `jisutrainf.market.alicloudapi.com/train/station2s` |",
        "",
        "> 航班/火车票为付费接口、免费额度极少，因此每个 MCP 都带 `mock_mode` 开关 + 模拟兜底。",
        "",
        "## 阅读路线总览",
        "",
        "| 步骤 | 文件 | 作用 |",
        "| --- | --- | --- |",
        "| 0 | README / requirements / .env.example | 整体印象与环境配置 |",
        "| 1 | `configs/settings.py` | 全局配置中心（API Key、端口、开关） |",
        "| 2 | `mcp_servers/base.py` | MCP 基类（共享 HTTP 客户端 + 兜底） |",
        "| 3 | `mcp_servers/city_codes.py` | 城市编码映射（adcode / IATA） |",
        "| 4 | `models/schemas.py` | Pydantic 数据结构 |",
        "| 5 | `models/database.py` | SQLAlchemy 数据库模型 |",
        "| 6 | `mcp_servers/weather_mcp.py` | 天气工具（高德） |",
        "| 7 | `mcp_servers/flight_mcp.py` | 航班工具（阿里云） |",
        "| 8 | `mcp_servers/train_mcp.py` | 火车票工具（阿里云） |",
        "| 9 | `mcp_servers/hotel_mcp.py` | 酒店工具（高德） |",
        "| 10 | `mcp_servers/db_mcp.py` | 数据库工具（增删改查） |",
        "| 11 | `agents/base_agent.py` | Agent 基类（A2A 协议） |",
        "| 12 | `agents/weather_agent.py` | 天气 Agent |",
        "| 13 | `agents/flight_agent.py` | 航班 Agent |",
        "| 14 | `agents/train_agent.py` | 火车票 Agent |",
        "| 15 | `agents/hotel_agent.py` | 酒店 Agent |",
        "| 16 | `agents/itinerary_agent.py` | 行程 Agent |",
        "| 17 | `core/intent_recognizer.py` | 意图识别（LLM + 规则） |",
        "| 18 | `core/slot_filler.py` | 槽位抽取（正则） |",
        "| 19 | `core/context_manager.py` | 会话上下文（内存） |",
        "| 20 | `orchestrator/agent_network.py` | Agent 注册中心 |",
        "| 21 | `orchestrator/router.py` | 任务路由（意图 → Agent） |",
        "| 22 | `orchestrator/workflows.py` | 旅行规划工作流 |",
        "| 23 | `api/dependencies.py` | 会话依赖注入 |",
        "| 24 | `api/routes/agent.py` | A2A 协议端点 |",
        "| 25 | `api/routes/chat.py` | 对话端点 |",
        "| 26 | `api/main.py` | FastAPI 应用入口 |",
        "| 27 | `web/app.py` | Streamlit 前端 |",
        "| 28 | 各 `__init__.py` | 包导出清单 |",
        "| 附录 | 依赖关系图 & 数据流 | 架构总览 |",
    ],
    [],
)

section(
    "## 第 0 步：先建立整体印象（README / 依赖 / 环境配置）",
    [
        "### 0.1 requirements.txt — 依赖清单",
        "",
        "注意：AI 编排使用 **langchain 1.x**，意图识别代码里用的是 `langchain_core.prompts` 和"
        " `ChatOpenAI(base_url=..., api_key=...)` 的新版写法。",
    ],
    [code_block("requirements.txt")],
)

section(
    "### 0.2 .env.example — 环境变量模板（API Key 已脱敏）",
    [
        "核心新增配置：`AMAP_API_KEY`（高德，天气+酒店）、`ALIYUN_APPCODE`（阿里云，航班+火车票）、"
        " `FLIGHT_MOCK_MODE` / `TRAIN_MOCK_MODE`（保护付费接口免费额度）。",
    ],
    [code_block(".env.example")],
)

# ================================================================
# 第 1 步 settings
# ================================================================
section(
    "## 第 1 步：configs/settings.py — 全局配置中心",
    [
        "用 `pydantic-settings` 从 `.env` 加载所有配置，任何模块 `from configs.settings import settings` 即可。",
        "",
        "关键点：",
        "- `amap_api_key` / `aliyun_appcode` 为必填（`Field(...)`），缺失会启动报错。",
        "- `flight_mock_mode` / `train_mock_mode` 默认 `True`（保护免费额度），天气/酒店默认 `False`（高德免费额度充足）。",
        "- 新增 `train_agent_port=5005` / `train_mcp_port=5014`。",
    ],
    [code_block("configs/settings.py")],
)

# ================================================================
# 第 2 步 base
# ================================================================
section(
    "## 第 2 步：mcp_servers/base.py — MCP 基类",
    [
        "所有 MCP 工具服务器（weather/flight/train/hotel/db）都继承 `BaseMCPServer`。",
        "",
        "职责：",
        "- 懒加载共享 `httpx.AsyncClient`（统一 15s 超时），提供 `get_json()` 便捷方法。",
        "- 提供统一的 `error(message)` 错误响应结构。",
        "- 提供 `mock_mode` 开关，子类据此决定走真实 API 还是模拟数据。",
    ],
    [code_block("mcp_servers/base.py")],
)

# ================================================================
# 第 3 步 city_codes
# ================================================================
section(
    "## 第 3 步：mcp_servers/city_codes.py — 城市编码映射",
    [
        "不同 API 对城市的编码要求不同：高德天气要 `adcode`，航班要 IATA 城市码。",
        "本模块维护静态映射表，并提供 `_lookup` 做三层解析：精确匹配 → 去后缀匹配 → 最长子串匹配"
        "（能正确处理「北京市」「四川省成都市」这类带行政后缀的输入）。",
    ],
    [code_block("mcp_servers/city_codes.py")],
)

# ================================================================
# 第 4 步 schemas
# ================================================================
section(
    "## 第 4 步：models/schemas.py — 数据结构定义（Pydantic）",
    [
        "定义了意图枚举、用户/行程/预订/聊天等 Schema，以及外部数据 Schema。",
        "",
        "本次新增：`IntentType.TRAIN_BOOKING`（高铁/火车票意图）与 `TrainData`（火车票数据模型）。",
    ],
    [code_block("models/schemas.py")],
)

# ================================================================
# 第 5 步 database
# ================================================================
section(
    "## 第 5 步：models/database.py — 数据库表与连接（SQLAlchemy）",
    [
        "三张表：`users` / `itineraries` / `bookings`，以及引擎/会话工厂等工具函数。",
        "本次未改表结构，仅补充了 `update_itinerary_status`、`cancel_booking` 两个操作方法"
        "（位于 `mcp_servers/db_mcp.py`，见第 10 步）。",
    ],
    [code_block("models/database.py")],
)

# ================================================================
# 第 6 步 weather_mcp
# ================================================================
section(
    "## 第 6 步：mcp_servers/weather_mcp.py — 天气工具（高德）",
    [
        "数据来源从「和风天气」切换为**高德开放平台**。",
        "",
        "关键点：",
        "- 高德天气接口要求 `city` 为 adcode：优先用静态映射（`city_to_adcode`），未知城市回退到地理编码接口动态解析（带内存缓存）。",
        "- `get_current_weather` → `extensions=base`（实况），返回 `lives`。",
        "- `get_forecast` → `extensions=all`（预报），返回 `forecasts[].casts`（最多 4 天）。",
        "- 失败自动降级为模拟数据，响应带 `source` 字段标识来源（`amap` / `mock`）。",
    ],
    [code_block("mcp_servers/weather_mcp.py")],
)

# ================================================================
# 第 7 步 flight_mcp
# ================================================================
section(
    "## 第 7 步：mcp_servers/flight_mcp.py — 航班工具（阿里云）",
    [
        "数据来源：阿里云 API 市场「全球飞机航班机票信息查询」。",
        "",
        "关键点：",
        "- 鉴权用请求头 `Authorization: APPCODE <appcode>`。",
        "- 出发/到达传 IATA 城市码（`city_to_iata`）。",
        "- 实测返回结构为 `result.flightInfo`，字段名如 `equipment`(机型)、`transferNum`(航段数)、"
        " `ticketPrice`(票价)、`departureName`(机场名)；`_normalize_flight_item` 做了防御性字段映射。",
        "- `transferNum=1` 表示直飞，故 `stops = transferNum - 1`。",
        "- 默认 `mock_mode` 开启保护免费额度。",
    ],
    [code_block("mcp_servers/flight_mcp.py")],
)

# ================================================================
# 第 8 步 train_mcp
# ================================================================
section(
    "## 第 8 步：mcp_servers/train_mcp.py — 火车票工具（阿里云）",
    [
        "本次新增。数据来源：阿里云 API 市场「全国火车票查询（极速数据）」。",
        "",
        "关键点：",
        "- `start`/`end` 直接传中文城市或车站名，`ishigh` 控制是否仅高铁。",
        "- 归一化后每条车次含 `train_no`、`train_type`、起止站/时刻、`seats`（各席别票价字典）和参考 `price`。",
        "- 同样带 mock 兜底（默认开启）。",
    ],
    [code_block("mcp_servers/train_mcp.py")],
)

# ================================================================
# 第 9 步 hotel_mcp
# ================================================================
section(
    "## 第 9 步：mcp_servers/hotel_mcp.py — 酒店工具（高德）",
    [
        "数据来源：高德「关键字搜索」`place/text`（keywords=酒店）。",
        "",
        "关键点：",
        "- 返回酒店名称/地址/区县/评分/电话/图片等；**高德不含实时房价**，`price_per_night` 用评分估算作参考。",
        "- `location` 存可读地址（城市+区县），`coords` 存经纬度。",
    ],
    [code_block("mcp_servers/hotel_mcp.py")],
)

# ================================================================
# 第 10 步 db_mcp
# ================================================================
section(
    "## 第 10 步：mcp_servers/db_mcp.py — 数据库工具（增删改查）",
    [
        "把数据库操作封装成 MCP 工具，供 itinerary Agent 调用。",
        "本次新增 `update_itinerary_status`（更新行程状态）与 `cancel_booking`（取消预订）。",
    ],
    [code_block("mcp_servers/db_mcp.py")],
)

# ================================================================
# 第 11 步 base_agent
# ================================================================
section(
    "## 第 11 步：agents/base_agent.py — Agent 基类（A2A 协议）",
    [
        "定义了 `Skill`（技能）、`AgentCard`（Agent 名片，A2A 发现用）和 `BaseAgent` 抽象基类。",
        "子类只需注册技能并实现 `skill_xxx` 方法，`execute_skill` 会自动按技能名分发。",
    ],
    [code_block("agents/base_agent.py")],
)

# ================================================================
# 第 12 步 weather_agent
# ================================================================
section(
    "## 第 12 步：agents/weather_agent.py — 天气 Agent",
    [
        "注册 `get_current_weather`、`get_forecast` 两个技能，直接透传给 weather_mcp。",
        "（原 `get_air_quality` 已移除，因为高德天气接口不提供空气质量数据。）",
    ],
    [code_block("agents/weather_agent.py")],
)

# ================================================================
# 第 13 步 flight_agent
# ================================================================
section(
    "## 第 13 步：agents/flight_agent.py — 航班 Agent",
    [
        "注册 `search_flights`、`get_flight_detail` 两个技能，透传给 flight_mcp。",
    ],
    [code_block("agents/flight_agent.py")],
)

# ================================================================
# 第 14 步 train_agent
# ================================================================
section(
    "## 第 14 步：agents/train_agent.py — 火车票 Agent",
    [
        "本次新增。注册 `search_trains` 技能，透传给 train_mcp。",
    ],
    [code_block("agents/train_agent.py")],
)

# ================================================================
# 第 15 步 hotel_agent
# ================================================================
section(
    "## 第 15 步：agents/hotel_agent.py — 酒店 Agent",
    [
        "注册 `search_hotels`、`get_hotel_detail` 两个技能，透传给 hotel_mcp。",
    ],
    [code_block("agents/hotel_agent.py")],
)

# ================================================================
# 第 16 步 itinerary_agent
# ================================================================
section(
    "## 第 16 步：agents/itinerary_agent.py — 行程 Agent",
    [
        "行程全生命周期管理，本次把技能从 4 个扩充到 6 个：",
        "`create_itinerary` / `get_user_itineraries` / `get_itinerary_detail` / "
        "`add_booking` / `update_itinerary_status` / `cancel_booking`。",
        "另有 `plan_itinerary` 便捷方法，串起「创建行程 → 加机票/酒店预订」。",
    ],
    [code_block("agents/itinerary_agent.py")],
)

# ================================================================
# 第 17 步 intent_recognizer
# ================================================================
section(
    "## 第 17 步：core/intent_recognizer.py — 意图识别（LLM + 规则兜底）",
    [
        "用 DeepSeek 做意图识别（6 种意图：weather/flight/train/hotel/itinerary/general），"
        "置信度不足时回退到关键词规则。",
        "",
        "注意：改用 **langchain 1.x** 写法 —— `from langchain_core.prompts import ChatPromptTemplate`，"
        " `ChatOpenAI(api_key=..., base_url=...)`。",
    ],
    [code_block("core/intent_recognizer.py")],
)

# ================================================================
# 第 18 步 slot_filler
# ================================================================
section(
    "## 第 18 步：core/slot_filler.py — 槽位抽取（正则）",
    [
        "用正则从自然语言中抽取目的地/出发地/日期/天数/预算/人数等槽位。",
        "本次新增：`从X去Y` 的出发地抽取，以及「高铁/动车/城际」关键词 → `is_high_speed` 槽位。",
    ],
    [code_block("core/slot_filler.py")],
)

# ================================================================
# 第 19 步 context_manager
# ================================================================
section(
    "## 第 19 步：core/context_manager.py — 会话上下文（内存）",
    [
        "内存版会话管理：创建/查询会话、记录消息、维护当前意图与槽位。",
        "（未做改动。）",
    ],
    [code_block("core/context_manager.py")],
)

# ================================================================
# 第 20 步 agent_network
# ================================================================
section(
    "## 第 20 步：orchestrator/agent_network.py — Agent 注册中心",
    [
        "管理所有 Agent 的注册/发现/调用，`invoke_agent` 是实际执行技能的入口。",
        "本次新增 `train` Agent 的注册。",
    ],
    [code_block("orchestrator/agent_network.py")],
)

# ================================================================
# 第 21 步 router
# ================================================================
section(
    "## 第 21 步：orchestrator/router.py — 任务路由（意图 → Agent）",
    [
        "核心路由逻辑：意图 → Agent → 技能，槽位名映射 + 默认值填充 + 缺失参数追问。",
        "",
        "本次新增：",
        "- `IntentType.TRAIN_BOOKING → train / search_trains`",
        "- train 槽位映射 `departure→start`、`destination→end`，日期默认明天。",
    ],
    [code_block("orchestrator/router.py")],
)

# ================================================================
# 第 22 步 workflows
# ================================================================
section(
    "## 第 22 步：orchestrator/workflows.py — 旅行规划工作流",
    [
        "串起多 Agent 协作：查天气 → 查航班 → 查酒店 → 创建行程 → 加预订。",
        "本次新增 `search_trains_only` 简化工作流。",
    ],
    [code_block("orchestrator/workflows.py")],
)

# ================================================================
# 第 23 步 dependencies
# ================================================================
section(
    "## 第 23 步：api/dependencies.py — 会话依赖注入",
    [
        "从请求头获取或创建会话 ID，供 FastAPI 依赖注入使用。（未做改动。）",
    ],
    [code_block("api/dependencies.py")],
)

# ================================================================
# 第 24 步 routes/agent
# ================================================================
section(
    "## 第 24 步：api/routes/agent.py — A2A 协议端点",
    [
        "暴露 Agent 列表 / Agent 名片 / 技能调用 / 网关名片等端点。",
        "本次在网关名片里补充了 `train_booking` 技能。",
    ],
    [code_block("api/routes/agent.py")],
)

# ================================================================
# 第 25 步 routes/chat
# ================================================================
section(
    "## 第 25 步：api/routes/chat.py — 对话端点",
    [
        "主对话入口：意图识别 → 路由 → 按 Agent 类型组装友好回复。",
        "本次新增 `train` 分支的回复组装。",
    ],
    [code_block("api/routes/chat.py")],
)

# ================================================================
# 第 26 步 main
# ================================================================
section(
    "## 第 26 步：api/main.py — FastAPI 应用入口",
    [
        "FastAPI 应用与生命周期（启动建表、关闭释放连接）、CORS、健康检查。（未做改动。）",
    ],
    [code_block("api/main.py")],
)

# ================================================================
# 第 27 步 web/app
# ================================================================
section(
    "## 第 27 步：web/app.py — Streamlit 前端",
    [
        "对话式 UI，根据意图展示天气卡片 / 航班列表 / 火车票列表 / 酒店列表。",
        "本次新增 `display_train_list`，并适配了新的天气/航班/酒店字段结构。",
    ],
    [code_block("web/app.py")],
)

# ================================================================
# 第 28 步 __init__
# ================================================================
section(
    "## 第 28 步：各 __init__.py — 包导出清单",
    [
        "各包导出符号清单，`mcp_servers/__init__.py` 新增 `BaseMCPServer`/`TrainMCPServer`，"
        "`agents/__init__.py` 新增 `TrainAgent`。",
    ],
    [
        code_block("mcp_servers/__init__.py"),
        code_block("agents/__init__.py"),
        code_block("models/__init__.py"),
        code_block("core/__init__.py"),
        code_block("orchestrator/__init__.py"),
        code_block("api/routes/__init__.py"),
    ],
)

# ================================================================
# 附录
# ================================================================
section(
    "## 附录：依赖关系图 & 数据流",
    [
        "### 依赖方向（自上而下）",
        "",
        "```text",
        "web/ → api/ → orchestrator/ → agents/ → mcp_servers/",
        "                  ↓              ↓",
        "                core/        (高德 / 阿里云 API)",
        "                  ↓",
        "               models/",
        "                  ↓",
        "              configs/",
        "```",
        "",
        "### 一次「查高铁票」请求的完整数据流",
        "",
        "```text",
        "用户输入「杭州到北京的高铁」",
        "  → web/app.py 调用 POST /api/chat/",
        "  → api/routes/chat.py: agent_router.route()",
        "  → core/intent_recognizer.py: 意图 = train_booking，槽位 = {departure:杭州, destination:北京}",
        "  → core/slot_filler.py: 补全 is_high_speed=1",
        "  → orchestrator/router.py: 槽位映射 departure→start, destination→end，日期默认明天",
        "  → orchestrator/agent_network.py: invoke_agent('train', 'search_trains', {...})",
        "  → agents/train_agent.py: skill_search_trains",
        "  → mcp_servers/train_mcp.py: 调阿里云火车票接口（或 mock 兜底）",
        "  → 结果原路返回，chat.py 组装「为您找到 N 趟车次」",
        "  → web/app.py: display_train_list 渲染",
        "```",
        "",
        "### 测试",
        "",
        "```bash",
        "pytest tests/ -v",
        "```",
        "",
        "测试全部走 mock 模式，不会消耗真实 API 额度（尤其是航班/火车票的免费调用次数）。",
        "",
        "### 切换到真实数据的开关",
        "",
        "在 `.env` 中设置：",
        "```text",
        "FLIGHT_MOCK_MODE=false   # 使用真实航班数据（会消耗免费额度）",
        "TRAIN_MOCK_MODE=false    # 使用真实火车票数据",
        "WEATHER_MOCK_MODE=false  # 天气（高德，默认已真实）",
        "HOTEL_MOCK_MODE=false    # 酒店（高德，默认已真实）",
        "```",
    ],
    [],
)


def main():
    parts = []
    for title, prose, blocks in S:
        parts.append(title)
        parts.append("")
        if prose:
            parts.append("\n".join(prose))
            parts.append("")
        for b in blocks:
            parts.append(b)
            parts.append("")
        parts.append("---")
        parts.append("")

    content = "\n".join(parts)
    with io.open(OUT, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"generated: {OUT} ({len(content)} chars)")


if __name__ == "__main__":
    main()
