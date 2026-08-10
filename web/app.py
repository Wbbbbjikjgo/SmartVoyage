"""Streamlit web frontend for SmartVoyage."""

import streamlit as st
import requests
import json
from typing import Dict, Any, Optional

# Page configuration
st.set_page_config(
    page_title="SmartVoyage - 智能旅行助手",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# API configuration
API_BASE_URL = "http://localhost:8000"


def init_session_state():
    """Initialize session state variables."""
    if "session_id" not in st.session_state:
        st.session_state.session_id = None
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "user_id" not in st.session_state:
        st.session_state.user_id = 1  # Default user for demo


def call_api(endpoint: str, data: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
    """
    Call API endpoint.

    Args:
        endpoint: API endpoint
        data: Request data

    Returns:
        Response data or None
    """
    try:
        url = f"{API_BASE_URL}{endpoint}"
        if data:
            response = requests.post(url, json=data, timeout=30)
        else:
            response = requests.get(url, timeout=30)

        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"API Error: {response.status_code}")
            return None
    except requests.exceptions.ConnectionError:
        st.error("无法连接到 API 服务，请确保 FastAPI 服务已启动。")
        return None
    except Exception as e:
        st.error(f"请求出错: {e}")
        return None


def display_weather_card(weather_data: Dict[str, Any]):
    """Display weather data as a card."""
    if weather_data.get("error"):
        st.warning(f"天气查询失败: {weather_data.get('message')}")
        return

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            label="🌡️ 温度",
            value=f"{weather_data.get('temperature', 'N/A')}°C",
        )

    with col2:
        st.metric(
            label="💧 湿度",
            value=f"{weather_data.get('humidity', 'N/A')}%",
        )

    with col3:
        st.metric(
            label="💨 风速",
            value=f"{weather_data.get('wind_speed', 'N/A')} km/h",
        )

    st.info(f"**{weather_data.get('location', '')}** - {weather_data.get('description', '')}")


def display_flight_list(flight_data: Dict[str, Any]):
    """Display flight search results."""
    if flight_data.get("error"):
        st.warning(f"航班查询失败: {flight_data.get('message')}")
        return

    flights = flight_data.get("flights", [])
    if not flights:
        st.info("未找到可用航班")
        return

    st.success(f"找到 {len(flights)} 个航班")

    for flight in flights[:5]:  # Show top 5
        with st.expander(f"✈️ {flight['flight_no']} - {flight['airline']}"):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.write(f"**出发**: {flight['departure_time']}")
                st.write(f"{flight['departure']} ({flight['departure_airport']})")
            with col2:
                st.write(f"**到达**: {flight['arrival_time']}")
                st.write(f"{flight['arrival']} ({flight['arrival_airport']})")
            with col3:
                st.write(f"**价格**: ¥{flight['price']}")
                st.write(f"**剩余座位**: {flight['available_seats']}")


def display_hotel_list(hotel_data: Dict[str, Any]):
    """Display hotel search results."""
    if hotel_data.get("error"):
        st.warning(f"酒店查询失败: {hotel_data.get('message')}")
        return

    hotels = hotel_data.get("hotels", [])
    if not hotels:
        st.info("未找到可用酒店")
        return

    st.success(f"找到 {len(hotels)} 家酒店")

    for hotel in hotels[:5]:  # Show top 5
        with st.expander(f"🏨 {hotel['hotel_name']}"):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**位置**: {hotel['location']}")
                st.write(f"**评分**: {'⭐' * int(hotel['rating'])} {hotel['rating']}")
            with col2:
                st.write(f"**价格**: ¥{hotel['price_per_night']}/晚")
                st.write(f"**设施**: {', '.join(hotel['amenities'][:4])}")


def render_sidebar():
    """Render sidebar with settings and info."""
    with st.sidebar:
        st.title("⚙️ 设置")

        st.subheader("🔌 服务状态")
        # Check API health
        health = call_api("/health")
        if health:
            st.success("✅ API 服务正常")
        else:
            st.error("❌ API 服务未连接")

        st.divider()

        st.subheader("📊 会话信息")
        st.write(f"**Session ID**: `{st.session_state.session_id or '未创建'}`")
        st.write(f"**User ID**: {st.session_state.user_id}")
        st.write(f"**消息数**: {len(st.session_state.messages)}")

        st.divider()

        st.subheader("💡 使用提示")
        st.markdown("""
        试试问我：
        - "北京今天天气怎么样？"
        - "帮我查一下上海到北京的机票"
        - "北京有什么酒店推荐？"
        - "帮我规划一个北京3日游"
        """)

        st.divider()

        if st.button("🔄 新建会话", use_container_width=True):
            st.session_state.session_id = None
            st.session_state.messages = []
            st.rerun()


def render_chat_interface():
    """Render main chat interface."""
    st.title("✈️ SmartVoyage 智能旅行助手")
    st.caption("基于 A2A 协议的多智能体协作系统")

    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

            # Display data cards if available
            if message.get("data"):
                data = message["data"]
                intent = message.get("intent")

                if intent == "weather_query":
                    display_weather_card(data)
                elif intent == "flight_booking":
                    display_flight_list(data)
                elif intent == "hotel_booking":
                    display_hotel_list(data)

    # Chat input
    if prompt := st.chat_input("请输入您的问题..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.chat_message("user"):
            st.markdown(prompt)

        # Get API response
        with st.chat_message("assistant"):
            with st.spinner("思考中..."):
                response = call_api("/api/chat/", {
                    "message": prompt,
                    "session_id": st.session_state.session_id,
                })

            if response:
                # Update session ID
                if not st.session_state.session_id:
                    st.session_state.session_id = response.get("session_id")

                # Display response
                message = response.get("message", "")
                st.markdown(message)

                # Display data if available
                data = response.get("data", {})
                intent = response.get("intent")

                if data and not data.get("error"):
                    actual_data = data.get("data", data)
                    if intent == "weather_query":
                        display_weather_card(actual_data)
                    elif intent == "flight_booking":
                        display_flight_list(actual_data)
                    elif intent == "hotel_booking":
                        display_hotel_list(actual_data)

                # Add to history
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": message,
                    "intent": intent,
                    "data": data.get("data") if data else None,
                })


def main():
    """Main entry point."""
    init_session_state()
    render_sidebar()
    render_chat_interface()


if __name__ == "__main__":
    main()
