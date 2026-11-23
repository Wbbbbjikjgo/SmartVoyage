"""Streamlit web frontend for SmartVoyage.

前端只负责调用 FastAPI 网关；网关再通过 A2A 协议调用远程 Agent。所有回答
都由各 Agent 的大模型基于真实 MCP 工具数据生成。
"""

import os
from typing import Any, Dict, Optional

import requests
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

st.set_page_config(
    page_title="SmartVoyage - 智能旅行助手",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded",
)


def init_session_state() -> None:
    """Initialize Streamlit session state."""
    if "session_id" not in st.session_state:
        st.session_state.session_id = None
    if "messages" not in st.session_state:
        st.session_state.messages = []


def call_api(endpoint: str, data: Optional[Dict[str, Any]] = None) -> Any:
    """Call the FastAPI gateway."""
    url = f"{API_BASE_URL}{endpoint}"
    try:
        if data is not None:
            response = requests.post(url, json=data, timeout=180)
        else:
            response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json()
        st.error(f"API 错误：HTTP {response.status_code}")
        return None
    except requests.exceptions.ConnectionError:
        st.error("无法连接到 API 服务，请确认网关（8000）已启动。")
        return None
    except Exception as exc:  # noqa: BLE001
        st.error(f"请求出错：{exc}")
        return None


def render_sidebar() -> None:
    """Render sidebar with service status and session info."""
    with st.sidebar:
        st.title("⚙️ 服务状态")

        if call_api("/health"):
            st.success("✅ API 网关正常")
        else:
            st.error("❌ API 网关未连接")

        agents = call_api("/api/agents/")
        if isinstance(agents, list) and agents:
            st.write("**已发现的 A2A Agent**")
            for agent in agents:
                st.caption(f"- {agent.get('name')} → {agent.get('url')}")
        else:
            st.warning("未发现 A2A Agent，请启动注册中心与各 Agent 服务")

        st.divider()
        st.subheader("📊 会话信息")
        st.write(f"**Session ID**：`{st.session_state.session_id or '未创建'}`")
        st.write(f"**消息数**：{len(st.session_state.messages)}")

        st.divider()
        st.subheader("💡 使用提示")
        st.markdown(
            """
            - 「北京今天天气怎么样？」
            - 「帮我查一下上海到北京的机票」
            - 「查一下杭州到北京的高铁票」
            - 「北京有什么酒店推荐？」
            - 「帮我规划一个北京3日游」
            """
        )

        st.divider()
        if st.button("🔄 新建会话", use_container_width=True):
            st.session_state.session_id = None
            st.session_state.messages = []
            st.rerun()


def render_chat_interface() -> None:
    """Render the main chat interface."""
    st.title("✈️ SmartVoyage 智能旅行助手")
    st.caption("真实 A2A Agent + 真实 MCP 工具 + 大模型自主决策")

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt = st.chat_input("请输入您的问题...")
    if not prompt:
        return

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("主 Agent 正在识别意图并调用远程 Agent..."):
            response = call_api(
                "/api/chat/",
                {
                    "message": prompt,
                    "session_id": st.session_state.session_id,
                },
            )

        if response:
            if not st.session_state.session_id:
                st.session_state.session_id = response.get("session_id")
            message = response.get("message", "")
            st.markdown(message)
            st.session_state.messages.append(
                {"role": "assistant", "content": message}
            )


def main() -> None:
    """Main entry point."""
    init_session_state()
    render_sidebar()
    render_chat_interface()


if __name__ == "__main__":
    main()
