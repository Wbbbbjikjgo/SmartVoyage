# SmartVoyage - 智能旅行助手

> 基于 A2A（Agent-to-Agent）协议的多智能体旅行规划系统

SmartVoyage 通过自然语言交互，让多个专用 Agent 协作完成天气查询、机票查询、酒店推荐与行程规划，并以对话式界面流式展示结果。

---

## ✨ 核心能力

| 能力 | 说明 |
| --- | --- |
| 🧠 LLM 意图识别 | 自然语言输入 → 意图分类 + 槽位提取 → 任务路由 |
| 🌤️ 天气查询 | 实时天气、天气预报、空气质量（支持 Mock 模式） |
| ✈️ 机票查询 | 多航司航班检索，含机型/准点率/折扣/经停等信息 |
| 🏨 酒店推荐 | 多城市酒店检索，含评分/标签/早餐/房型等详情 |
| 🗺️ 行程规划 | 结合天气与票务结果生成完整行程，并持久化到数据库 |
| 💬 对话式 UI | Streamlit 前端，流式展示 AI 回复 |

智能默认值：查询机票/酒店/规划行程时未指定日期，系统自动默认「明天」出发，无需反复追问。

---

## 🏗️ 技术架构

```text
web/ → api/ → orchestrator/ → agents/ → mcp_servers/
                  ↓
                core/  （意图识别、槽位填充、上下文管理）
                  ↓
               models/  （Pydantic Schema + SQLAlchemy 模型）
                  ↓
              configs/  （配置管理）
```

### 技术栈

| 层级 | 技术 | 用途 |
| --- | --- | --- |
| 前端 | Streamlit | 对话式 UI，支持流式输出 |
| API 网关 | FastAPI + Uvicorn | RESTful API + A2A 协议承载 |
| A2A 协议 | python-a2a（可降级为自建实现） | Agent 发现、通信、工作流 |
| AI 编排 | LangChain | LLM 集成、工具调用 |
| LLM | DeepSeek（兼容 OpenAI 格式） | 意图识别、回答生成 |
| 工具调用 | MCP | Agent 调用外部工具 |
| 数据库 | MySQL 8.0（本地） | 持久化存储 |
| 缓存 | Redis（本地，可选） | 会话管理 |
| 日志 | Elasticsearch（Docker，可选） | 日志分析 |

### 模块职责

| 模块 | 职责 |
| --- | --- |
| `agents/` | A2A Agent 实现（天气/航班/酒店/行程） |
| `mcp_servers/` | MCP 工具服务器，封装外部 API / 模拟数据 |
| `orchestrator/` | 工作流编排、Agent 网络、任务路由 |
| `core/` | 意图识别、槽位填充、上下文管理 |
| `api/` | FastAPI 网关与 A2A 端点 |
| `web/` | Streamlit 前端 |
| `models/` | 数据模型 |
| `configs/` | 配置管理 |

---

## 🚀 快速开始

### 1. 环境要求

- Python 3.11+
- MySQL 8.0（本地）
- Redis（本地，可选）

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，填入你的 API Key：

| 变量 | 说明 |
| --- | --- |
| `OPENAI_API_KEY` | DeepSeek API Key |
| `OPENAI_BASE_URL` | 默认 `https://api.deepseek.com` |
| `OPENAI_MODEL` | 默认 `deepseek-chat` |
| `QWEATHER_API_KEY` | 和风天气 API Key（Mock 模式下可不填） |
| `MYSQL_PASSWORD` | 本地 MySQL 密码 |

> `QWEATHER_MOCK_MODE` 默认 `True`，未配置天气 Key 时自动返回模拟数据。

### 4. 启动服务（按顺序）

| 顺序 | 服务 | 命令 | 端口 |
| --- | --- | --- | --- |
| 1 | 基础设施 | 启动本地 MySQL / Redis | 3306 / 6379 |
| 2 | API 网关 | `uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload` | 8000 |
| 3 | 前端 | `streamlit run web/app.py --server.port 8501` | 8501 |

> 说明：当前版本 Agent 与 MCP 均在网关进程内以本地对象运行，无需单独启动 5001-5004 / 5010-5013 端口服务；如需分布式部署，可参考 `deploy/` 与 `docs/`。

### 5. 访问

- 前端界面：http://localhost:8501
- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

---

## 💬 使用示例

试试以下提问：

- 「北京今天天气怎么样」
- 「帮我查一下上海到北京的机票」
- 「北京有什么酒店推荐」
- 「帮我规划一个北京3日游」

---

## 🗂️ 项目结构

```text
SmartVoyage/
├── agents/            # A2A Agent（weather/flight/hotel/itinerary + base）
├── api/
│   ├── routes/        # chat / agent 路由
│   └── main.py        # FastAPI 入口
├── core/              # 意图识别、槽位填充、上下文管理
├── orchestrator/      # Agent 网络、路由、旅行规划工作流
├── mcp_servers/       # 天气/航班/酒店/数据库 MCP 工具
├── models/            # SQLAlchemy 模型 + Pydantic Schema
├── configs/           # 配置管理
├── web/               # Streamlit 前端
├── tests/             # 测试目录
├── docs/              # 技术文档
├── .env.example       # 环境变量模板
└── requirements.txt   # Python 依赖
```

---

## 🧪 测试

```bash
pytest tests/ -v
```

---

## 📜 开发约定

- 遵循 PEP 8，使用 4 空格缩进
- 所有公开函数/类添加 docstring 与类型注解
- Git 提交遵循 Conventional Commits（`feat`/`fix`/`docs`/`refactor`...）
- 配置项统一放在 `configs/settings.py`，从环境变量读取
- 日志使用 `logging` 模块，不使用 `print`

详见 [AGENTS.md](AGENTS.md)。

---

## 📄 许可证

仅供学习与技术演示使用。
