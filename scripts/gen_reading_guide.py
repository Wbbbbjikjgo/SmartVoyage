# -*- coding: utf-8 -*-
"""Regenerate docs/从0到1源码阅读指南.md from the current source tree.

Usage::

    python scripts/gen_reading_guide.py

The generated guide documents the real A2A + MCP architecture:

    web -> api -> orchestrator --A2A HTTP--> agents -> MCP stdio -> external APIs/MySQL
"""

import io
import os
from datetime import datetime
from typing import List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "从0到1源码阅读指南.md")

SECTIONS: List[Tuple[str, List[str], List[Tuple[str, str]]]] = []


def read(path: str) -> str:
    """Read a source file relative to the project root."""
    with io.open(os.path.join(ROOT, path), "r", encoding="utf-8") as handle:
        return handle.read()


def code_block(path: str, lang: str = "python") -> str:
    """Render a source file as a fenced code block."""
    return f"#### `{path}`\n\n```{lang}\n{read(path).rstrip()}\n```\n"


def section(
    title: str,
    prose: List[str],
    files: Optional[List[Tuple[str, str]]] = None,
) -> None:
    """Register a guide section."""
    SECTIONS.append((title, prose, files or []))


# ================================================================
# 0. 总览
# ================================================================
section(
    "# SmartVoyage 从 0 到 1 源码阅读指南",
    [
        "> 本指南按真实调用链路组织章节，读完可以完整理解 SmartVoyage 的",
        "> **A2A（Agent-to-Agent）+ MCP（Model Context Protocol）+ 大模型** 实现。",
        "",
        f"> 自动生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 这个项目是什么",
        "",
        "SmartVoyage 是一个多智能体旅行助手：用户用自然语言提出需求，主 Agent",
        "识别意图后，通过标准 A2A 协议 HTTP 调用对应的远程 Agent；每个 Agent 都",
        "拥有自己的大模型，并通过真正的 MCP stdio 协议调用真实外部工具。",
        "",
        "```text",
        "Streamlit (8501)",
        "      │ HTTP",
        "      ▼",
        "FastAPI 主 Agent (8000)",
        "  意图识别 → 注册中心发现 URL → A2A HTTP 调用",
        "      │",
        "      ▼",
        "weather(5001) flight(5002) hotel(5003) itinerary(5004) train(5005)",
        "      │ stdio MCP",
        "      ▼",
        "weather_mcp  flight_mcp  hotel_mcp  train_mcp  db_mcp",
        "      │",
        "      ▼",
        "高德开放平台 / 阿里云 API 市场 / MySQL",
        "```",
        "",
        "### 三条必须记住的约束",
        "",
        "1. **没有 mock**：所有数据来自真实接口；缺少 Key 或接口失败时只返回明确错误。",
        "2. **MCP 是真的 MCP**：工具用 `@mcp.tool()` 注册，Agent 通过 MCP Client/Adapter 发现并调用。",
        "3. **A2A 是真的 A2A**：Agent 之间只通过 HTTP URL 通信，禁止进程内直接 import 调用。",
        "",
        "### 推荐阅读顺序",
        "",
        "| 步骤 | 文件 | 作用 |",
        "| --- | --- | --- |",
        "| 0 | README / requirements / .env.example | 环境与依赖 |",
        "| 1 | `configs/settings.py` | 配置中心 |",
        "| 2 | `models/` | 数据结构与数据库模型 |",
        "| 3 | `mcp_servers/*.py` | 真实 MCP Server（`@mcp.tool()`） |",
        "| 4 | `core/mcp_client.py` / `core/mcp_tool_adapter.py` | MCP 客户端与 LangChain Tool 适配 |",
        "| 5 | `core/llm.py` / `core/intent_recognizer.py` / `core/slot_filler.py` | 大模型、意图、槽位 |",
        "| 6 | `agents/` | 每个 A2A Agent（自己的大模型 + MCP 工具） |",
        "| 7 | `registry/` + `core/registry_client.py` | A2A 注册与发现 |",
        "| 8 | `orchestrator/` | 主 Agent 路由与多 Agent 工作流 |",
        "| 9 | `api/` | FastAPI 网关 |",
        "| 10 | `web/` | Streamlit 前端 |",
        "| 11 | `scripts/start_all.py` | 一键启动 |",
    ],
)

# ================================================================
# 1. 环境与配置
# ================================================================
section(
    "## 1. 环境与配置",
    [
        "先看依赖与配置，理解每个外部 Key 的用途。",
        "",
        "关键配置项：",
        "",
        "- `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL`：DeepSeek 兼容接口。",
        "- `AMAP_API_KEY`：高德天气、酒店、景点。",
        "- `ALIYUN_APPCODE`：阿里云航班、火车票。",
        "- `REGISTRY_URL`：A2A 注册中心地址。",
        "- `*_AGENT_PORT`：每个 A2A Agent 的 HTTP 端口。",
        "",
        "MCP Server 通过 stdio 通信，**不占用端口**。",
    ],
    [
        ("requirements.txt", "text"),
        (".env.example", "text"),
        ("configs/settings.py", "python"),
    ],
)

# ================================================================
# 2. 数据模型
# ================================================================
section(
    "## 2. 数据模型",
    [
        "`models/schemas.py` 定义意图、槽位、行程等 Pydantic 结构；",
        "`models/database.py` 定义 MySQL 表结构与 SQLAlchemy 会话。",
        "",
        "真正的行程写入由 Itinerary Agent 通过 `db_mcp` 工具完成。",
    ],
    [
        ("models/schemas.py", "python"),
        ("models/database.py", "python"),
    ],
)

# ================================================================
# 3. MCP Server
# ================================================================
section(
    "## 3. 真正的 MCP Server（stdio + `@mcp.tool()`）",
    [
        "每个 `mcp_servers/*.py` 都是一个可独立运行的 MCP Server：",
        "",
        "```bash",
        "python -m mcp_servers.weather_mcp",
        "python -m mcp_servers.flight_mcp",
        "python -m mcp_servers.train_mcp",
        "python -m mcp_servers.hotel_mcp",
        "python -m mcp_servers.db_mcp",
        "```",
        "",
        "要点：",
        "",
        "- `FastMCP(\"...\")` 创建 MCP Server；",
        "- `@mcp.tool()` 注册真实工具；",
        "- `mcp.run(transport=\"stdio\")` 启动；",
        "- 日志必须写 stderr，绝不能污染 stdout（stdout 是 JSON-RPC 通道）；",
        "- 所有工具只调用真实接口，失败返回明确错误。",
    ],
    [
        ("mcp_servers/base.py", "python"),
        ("mcp_servers/city_codes.py", "python"),
        ("mcp_servers/weather_mcp.py", "python"),
        ("mcp_servers/flight_mcp.py", "python"),
        ("mcp_servers/train_mcp.py", "python"),
        ("mcp_servers/hotel_mcp.py", "python"),
        ("mcp_servers/db_mcp.py", "python"),
    ],
)

# ================================================================
# 4. MCP Client + Adapter
# ================================================================
section(
    "## 4. MCP Client 与 LangChain Tool 适配",
    [
        "这一层解决“Agent 如何拿到 MCP 工具”的问题：",
        "",
        "1. `MCPClient` 通过 stdio 启动 MCP Server 并完成握手；",
        "2. `MCPToolAdapter` 调用 `list_tools()` 拿到工具列表；",
        "3. 把 MCP 的 JSON Schema 转成 Pydantic 模型；",
        "4. 包装成 LangChain `StructuredTool`，交给 `create_agent(tools=...)`。",
        "",
        "`MCPToolset` 负责保持 MCP 连接存活并在 Agent 退出时统一关闭。",
    ],
    [
        ("core/mcp_client.py", "python"),
        ("core/mcp_tool_adapter.py", "python"),
    ],
)

# ================================================================
# 5. 大模型与主 Agent 前置能力
# ================================================================
section(
    "## 5. 大模型、意图识别、槽位与上下文",
    [
        "`core/llm.py` 统一创建 DeepSeek 客户端；缺少 Key 时抛出明确错误。",
        "",
        "意图识别优先用大模型，失败时降级为关键词规则（不伪造数据）；",
        "槽位填充负责提取出发地、目的地、日期、天数、人数、预算等。",
    ],
    [
        ("core/llm.py", "python"),
        ("core/intent_recognizer.py", "python"),
        ("core/slot_filler.py", "python"),
        ("core/context_manager.py", "python"),
    ],
)

# ================================================================
# 6. A2A Agent
# ================================================================
section(
    "## 6. 真正的 A2A Agent（每个 Agent 自己的大模型 + MCP 工具）",
    [
        "每个 Agent 都是一个独立的 A2A HTTP 服务：",
        "",
        "```bash",
        "python -m agents.weather",
        "python -m agents.flight",
        "python -m agents.train",
        "python -m agents.hotel",
        "python -m agents.itinerary",
        "```",
        "",
        "目录约定：",
        "",
        "- `agent_executor.py`：功能实现（继承 `ToolAwareAgentExecutor`，指定 MCP 模块与 system prompt）；",
        "- `__main__.py`：写 AgentCard 描述、技能列表，暴露 HTTP URL，并向注册中心注册。",
        "",
        "执行流程：",
        "",
        "```text",
        "A2A 请求",
        "  → 懒加载 MCPToolset（stdio 启动 MCP Server）",
        "  → 把工具交给本 Agent 的大模型",
        "  → 大模型自主选择 MCP 工具并读取真实数据",
        "  → 生成最终文本，作为 A2A Artifact 返回",
        "```",
    ],
    [
        ("agents/base_executor.py", "python"),
        ("agents/server.py", "python"),
        ("agents/weather/agent_executor.py", "python"),
        ("agents/weather/__main__.py", "python"),
        ("agents/flight/agent_executor.py", "python"),
        ("agents/flight/__main__.py", "python"),
        ("agents/train/agent_executor.py", "python"),
        ("agents/train/__main__.py", "python"),
        ("agents/hotel/agent_executor.py", "python"),
        ("agents/hotel/__main__.py", "python"),
        ("agents/itinerary/agent_executor.py", "python"),
        ("agents/itinerary/__main__.py", "python"),
    ],
)

# ================================================================
# 7. 注册中心
# ================================================================
section(
    "## 7. A2A 注册中心与心跳",
    [
        "Agent 启动后向注册中心注册自己的 AgentCard URL，并定时发送心跳；",
        "主 Agent 通过 `GET /.well-known/agents` 发现所有在线 Agent。",
        "",
        "注册中心不可用时，主 Agent 会回退到 `configs/settings.py` 中的静态端口配置。",
    ],
    [
        ("registry/server.py", "python"),
        ("core/registry_client.py", "python"),
    ],
)

# ================================================================
# 8. 编排
# ================================================================
section(
    "## 8. 主 Agent 路由与多 Agent 工作流",
    [
        "`orchestrator/router.py` 负责：",
        "",
        "1. 大模型意图识别；",
        "2. 槽位提取与参数映射；",
        "3. 根据意图选择 Agent；",
        "4. 通过注册中心解析 Agent URL；",
        "5. 用标准 A2A 客户端发送消息并返回答案。",
        "",
        "`orchestrator/workflows.py` 负责行程规划：依次调用 Weather、Hotel（酒店/景点）、",
        "Flight、Train，再把真实数据交给 Itinerary Agent 生成逐日计划并写入 MySQL。",
        "",
        "`orchestrator/a2a_client.py` 使用 `A2ACardResolver` + `A2AClient`，不直接 import Agent。",
    ],
    [
        ("orchestrator/a2a_client.py", "python"),
        ("orchestrator/agent_directory.py", "python"),
        ("orchestrator/router.py", "python"),
        ("orchestrator/workflows.py", "python"),
    ],
)

# ================================================================
# 9. API 网关
# ================================================================
section(
    "## 9. FastAPI 网关",
    [
        "API 网关不直接执行业务工具调用，只负责：",
        "",
        "- `/api/chat/`：调用主 Agent 路由；",
        "- `/api/chat/plan`：直接触发多 Agent 规划工作流；",
        "- `/api/agents/`：从注册中心发现 Agent；",
        "- `/api/agents/{name}/card`：拉取远程 AgentCard；",
        "- `/api/agents/{name}/invoke`：通过 A2A 直接调用指定 Agent。",
    ],
    [
        ("api/main.py", "python"),
        ("api/routes/chat.py", "python"),
        ("api/routes/agent.py", "python"),
    ],
)

# ================================================================
# 10. 前端与启动
# ================================================================
section(
    "## 10. Streamlit 前端与一键启动",
    [
        "前端只调用 FastAPI 网关，展示 Agent 返回的真实回答。",
        "",
        "一键启动：",
        "",
        "```bash",
        "python scripts/start_all.py          # 注册中心 + 5 个 Agent + API + 前端",
        "python scripts/start_all.py --no-web # 只启动后端",
        "```",
    ],
    [
        ("web/app.py", "python"),
        ("scripts/start_all.py", "python"),
    ],
)

# ================================================================
# 11. 测试
# ================================================================
section(
    "## 11. 测试",
    [
        "```bash",
        "pytest tests/ -v",
        "```",
        "",
        "重点测试：",
        "",
        "- 每个 MCP Server 确实注册了 `@mcp.tool()`；",
        "- 缺少 Key / 上游失败时返回明确错误（无 mock 降级）；",
        "- 真实返回结构的字段归一化；",
        "- 主 Agent 意图 → Agent/Skill → 参数 → 远程 URL 调用的路由逻辑。",
    ],
    [
        ("tests/test_mcp_servers.py", "python"),
        ("tests/test_router.py", "python"),
    ],
)


def render() -> str:
    """Render all registered sections into Markdown."""
    lines: List[str] = []
    for index, (title, prose, files) in enumerate(SECTIONS):
        if index == 0:
            lines.append(title)
        else:
            lines.append(f"\n{title}")
        lines.append("")
        if prose:
            lines.extend(prose)
            lines.append("")
        for path, lang in files:
            lines.append(code_block(path, lang))
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    """Generate the guide file."""
    content = render()
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)
    print(f"generated: {OUT}")
    print(f"sections: {len(SECTIONS)}, chars: {len(content)}")


if __name__ == "__main__":
    main()
