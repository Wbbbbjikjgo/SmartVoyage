# SmartVoyage - 智能旅行助手

> 基于 A2A（Agent-to-Agent）协议的多智能体旅行规划系统

SmartVoyage 通过自然语言交互，让多个专用 Agent 协作完成天气查询、机票查询、酒店推荐与行程规划，并以对话式界面流式展示结果。

---

## ✨ 核心能力

| 能力 | 说明 |
| --- | --- |
| 🧠 LLM 意图识别 | 自然语言输入 → 意图分类 + 槽位提取 → 任务路由 |
| 🌤️ 天气查询 | 实时天气、天气预报（高德开放平台，支持 Mock 降级） |
| ✈️ 机票查询 | 国内/国际航班检索（阿里云 API 市场，含机型/准点率等） |
| 🚄 高铁查询 | 高铁/动车/火车票检索，含各席别票价（阿里云 API 市场） |
| 🏨 酒店推荐 | 城市酒店检索，含评分/地址/电话等（高德 POI 搜索） |
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
| A2A 协议 | 自建实现（Agent Card + 技能调用） | Agent 发现、通信、工作流 |
| AI 编排 | LangChain 1.x | LLM 集成、意图识别 |
| LLM | DeepSeek（兼容 OpenAI 格式） | 意图识别、回答生成 |
| 外部数据 | 高德开放平台 / 阿里云 API 市场 | 天气、酒店、航班、火车票 |
| 工具调用 | MCP（进程内工具服务器） | Agent 调用外部工具 |
| 数据库 | MySQL 8.0（本地） | 持久化存储 |
| 缓存 | Redis（本地，可选） | 会话管理 |

### 模块职责

| 模块 | 职责 |
| --- | --- |
| `agents/` | A2A Agent 实现（天气/航班/火车票/酒店/行程） |
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
| `AMAP_API_KEY` | 高德开放平台 Web 服务 Key（天气 + 酒店） |
| `ALIYUN_APPCODE` | 阿里云 API 市场 AppCode（航班 + 火车票） |
| `MYSQL_PASSWORD` | 本地 MySQL 密码 |

> 航班/火车票为阿里云付费接口，免费额度极少，默认 `FLIGHT_MOCK_MODE` / `TRAIN_MOCK_MODE` 为 `true` 以保护额度；确认配额充足后再改为 `false`。

### 4. 初始化数据库

先确保本地 MySQL 已启动，然后创建数据库（表结构会在应用启动时自动创建）：

```bash
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS smartvoyage CHARACTER SET utf8mb4;"
```

### 5. 启动服务（需要两个终端）

**终端 1 —— 启动 API 网关（端口 8000）：**

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

**终端 2 —— 启动前端（端口 8501）：**

```bash
streamlit run web/app.py --server.port 8501
```

> 说明：当前版本 Agent 与 MCP 均在网关进程内以本地对象运行，无需单独启动 5001-5005 / 5010-5014 端口服务；如需分布式部署，可参考 `deploy/` 与 `docs/`。

### 6. 访问

| 入口 | 地址 |
| --- | --- |
| 前端界面 | http://localhost:8501 |
| API 文档（Swagger） | http://localhost:8000/docs |
| 健康检查 | http://localhost:8000/health |

---

## 💬 使用示例

试试以下提问：

- 「北京今天天气怎么样」
- 「帮我查一下上海到北京的机票」
- 「查一下杭州到北京的高铁票」
- 「北京有什么酒店推荐」
- 「帮我规划一个北京3日游」

---

## 🗂️ 项目结构

```text
SmartVoyage/
├── agents/            # A2A Agent（weather/flight/train/hotel/itinerary + base）
├── api/
│   ├── routes/        # chat / agent 路由
│   └── main.py        # FastAPI 入口
├── core/              # 意图识别、槽位填充、上下文管理
├── orchestrator/      # Agent 网络、路由、旅行规划工作流
├── mcp_servers/       # 天气/航班/火车票/酒店/数据库 MCP 工具
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
