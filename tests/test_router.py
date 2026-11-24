"""Tests for the main agent router (no LLM / no network)."""

import pytest

from core.context_manager import context_manager
from models.schemas import IntentResult, IntentType
from orchestrator.router import agent_router


@pytest.mark.asyncio
async def test_route_weather_calls_remote_url(monkeypatch):
    """Weather intent should be sent to the remote weather agent via A2A."""
    captured = {}

    async def fake_recognize(user_input):
        return IntentResult(
            intent=IntentType.WEATHER_QUERY,
            confidence=0.9,
            slots={"destination": "北京"},
        )

    async def fake_invoke(agent, prompt):
        captured["agent"] = agent
        captured["prompt"] = prompt
        return "http://127.0.0.1:5001", "北京现在晴，25°C。"

    monkeypatch.setattr(
        agent_router.intent_recognizer, "recognize_with_fallback", fake_recognize
    )
    monkeypatch.setattr(agent_router, "_invoke_remote", fake_invoke)

    result = await agent_router.route("北京天气怎么样")

    assert result["agent"] == "weather"
    assert result["data"]["answer"] == "北京现在晴，25°C。"
    assert captured["agent"] == "weather"
    assert "get_current_weather" in captured["prompt"]
    assert "北京" in captured["prompt"]


@pytest.mark.asyncio
async def test_route_train_maps_slots(monkeypatch):
    """Train intent maps slots (departure->start, destination->end)."""
    captured = {}

    async def fake_recognize(user_input):
        return IntentResult(
            intent=IntentType.TRAIN_BOOKING,
            confidence=0.9,
            slots={"departure": "杭州", "destination": "北京"},
        )

    async def fake_invoke(agent, prompt):
        captured["agent"] = agent
        captured["prompt"] = prompt
        return "http://127.0.0.1:5005", "找到若干车次。"

    monkeypatch.setattr(
        agent_router.intent_recognizer, "recognize_with_fallback", fake_recognize
    )
    monkeypatch.setattr(agent_router, "_invoke_remote", fake_invoke)

    result = await agent_router.route("杭州到北京的高铁")

    assert result["agent"] == "train"
    assert captured["agent"] == "train"
    assert '"start": "杭州"' in captured["prompt"]
    assert '"end": "北京"' in captured["prompt"]


@pytest.mark.asyncio
async def test_route_missing_slots_interrupts(monkeypatch):
    """Missing required slots should interrupt and ask, not call the agent."""

    async def fake_recognize(user_input):
        return IntentResult(
            intent=IntentType.TRAIN_BOOKING,
            confidence=0.9,
            slots={},
        )

    async def fake_invoke(agent, prompt):
        raise AssertionError("should not be invoked when slots are missing")

    monkeypatch.setattr(
        agent_router.intent_recognizer, "recognize_with_fallback", fake_recognize
    )
    monkeypatch.setattr(agent_router, "_invoke_remote", fake_invoke)

    result = await agent_router.route("帮我订个车票")

    assert result["success"] is True
    assert result["needs_input"] is True
    assert set(result["missing_slots"]) == {"start", "end"}
    assert "出发城市" in result["question"]


@pytest.mark.asyncio
async def test_weather_interrupt_then_resume(monkeypatch):
    """A missing location should be asked, then resumed with the user's answer."""
    session_id = context_manager.create_session()
    invocations = []

    async def fake_recognize(user_input):
        return IntentResult(
            intent=IntentType.WEATHER_QUERY, confidence=0.9, slots={}
        )

    async def fake_invoke(agent, prompt):
        invocations.append((agent, prompt))
        return "http://127.0.0.1:5001", "北京晴，25°C。"

    monkeypatch.setattr(
        agent_router.intent_recognizer, "recognize_with_fallback", fake_recognize
    )
    monkeypatch.setattr(agent_router, "_invoke_remote", fake_invoke)

    first = await agent_router.route("查一下天气", session_id=session_id)
    assert first["needs_input"] is True
    assert first["missing_slots"] == ["location"]
    assert not invocations

    second = await agent_router.route("北京", session_id=session_id)
    assert second["success"] is True
    assert second["data"]["answer"] == "北京晴，25°C。"
    assert invocations and invocations[0][0] == "weather"
    assert context_manager.get_pending_task(session_id) is None

    context_manager.clear_session(session_id)


@pytest.mark.asyncio
async def test_flight_interrupt_date_then_resume(monkeypatch):
    """Flight search should ask for the date, then resume once provided."""
    session_id = context_manager.create_session()
    invocations = []

    async def fake_recognize(user_input):
        return IntentResult(
            intent=IntentType.FLIGHT_BOOKING,
            confidence=0.9,
            slots={"departure": "北京", "destination": "上海"},
        )

    async def fake_invoke(agent, prompt):
        invocations.append((agent, prompt))
        return "http://127.0.0.1:5002", "找到多个航班。"

    monkeypatch.setattr(
        agent_router.intent_recognizer, "recognize_with_fallback", fake_recognize
    )
    monkeypatch.setattr(agent_router, "_invoke_remote", fake_invoke)

    first = await agent_router.route("北京到上海的机票", session_id=session_id)
    assert first["needs_input"] is True
    assert first["missing_slots"] == ["date"]
    assert not invocations

    second = await agent_router.route("明天", session_id=session_id)
    assert second["success"] is True
    assert invocations and invocations[0][0] == "flight"
    assert '"date"' in invocations[0][1]

    context_manager.clear_session(session_id)


@pytest.mark.asyncio
async def test_pending_task_can_be_cancelled(monkeypatch):
    """User can cancel an interrupted task with 取消."""
    session_id = context_manager.create_session()

    async def fake_recognize(user_input):
        return IntentResult(
            intent=IntentType.WEATHER_QUERY, confidence=0.9, slots={}
        )

    async def fake_invoke(agent, prompt):
        raise AssertionError("should not be invoked after cancel")

    monkeypatch.setattr(
        agent_router.intent_recognizer, "recognize_with_fallback", fake_recognize
    )
    monkeypatch.setattr(agent_router, "_invoke_remote", fake_invoke)

    await agent_router.route("查天气", session_id=session_id)
    result = await agent_router.route("取消", session_id=session_id)

    assert result["cancelled"] is True
    assert context_manager.get_pending_task(session_id) is None
    context_manager.clear_session(session_id)


def test_prepare_parameters_flight_keeps_date():
    params = agent_router._prepare_parameters(
        "flight",
        "search_flights",
        {"departure": "北京", "destination": "上海", "date": "2026-08-20"},
    )
    assert params["departure"] == "北京"
    assert params["arrival"] == "上海"
    assert params["date"] == "2026-08-20"


def test_prepare_parameters_hotel_keeps_guests():
    params = agent_router._prepare_parameters(
        "hotel",
        "search_hotels",
        {"destination": "北京", "date": "2026-08-20", "guests": 2},
    )
    assert params["location"] == "北京"
    assert params["check_in"] == "2026-08-20"
    assert params["guests"] == 2
    # 没有明确退房日期时，不伪造 check_out
    assert "check_out" not in params


@pytest.mark.asyncio
async def test_route_itinerary_planning(monkeypatch):
    """Itinerary intent goes through the multi-agent workflow."""

    async def fake_recognize(user_input):
        return IntentResult(
            intent=IntentType.ITINERARY_PLANNING,
            confidence=0.9,
            slots={"destination": "北京", "duration": 3, "date": "2026-08-20"},
        )

    captured = {}

    async def fake_execute(**kwargs):
        captured.update(kwargs)
        return {"success": True, "answer": "北京三日游计划（真实数据）"}

    monkeypatch.setattr(
        agent_router.intent_recognizer, "recognize_with_fallback", fake_recognize
    )
    from orchestrator.workflows import travel_workflow

    monkeypatch.setattr(travel_workflow, "execute", fake_execute)

    result = await agent_router.route("帮我规划一个北京3日游")

    assert result["agent"] == "itinerary"
    assert captured["destination"] == "北京"
    assert captured["duration"] == 3
    assert captured["start_date"] == "2026-08-20"
    assert result["data"]["answer"] == "北京三日游计划（真实数据）"


@pytest.mark.asyncio
async def test_itinerary_missing_start_date_then_resume(monkeypatch):
    """Itinerary planning should ask for start_date before calling the workflow."""
    session_id = context_manager.create_session()
    captured = {}

    async def fake_recognize(user_input):
        return IntentResult(
            intent=IntentType.ITINERARY_PLANNING,
            confidence=0.9,
            slots={"destination": "北京", "duration": 3},
        )

    async def fake_execute(**kwargs):
        captured.update(kwargs)
        return {"success": True, "answer": "北京三日游计划"}

    monkeypatch.setattr(
        agent_router.intent_recognizer, "recognize_with_fallback", fake_recognize
    )
    from orchestrator.workflows import travel_workflow

    monkeypatch.setattr(travel_workflow, "execute", fake_execute)

    first = await agent_router.route("规划北京3日游", session_id=session_id)
    assert first["needs_input"] is True
    assert first["missing_slots"] == ["start_date"]
    assert not captured

    second = await agent_router.route("明天", session_id=session_id)
    assert second["success"] is True
    assert captured["destination"] == "北京"
    assert captured["duration"] == 3
    assert captured["start_date"]  # 已由“明天”解析为具体日期

    context_manager.clear_session(session_id)


def test_build_day_plan():
    """逐日行程应均分景点并附带天气（规则工具函数，使用真实数据输入）。"""
    from core.itinerary_planner import build_day_plan

    weather = {"forecast": [{"day_weather": "晴", "day_temp": 31, "night_temp": 21}]}
    attractions = [
        {"name": "A"}, {"name": "B"}, {"name": "C"},
        {"name": "D"}, {"name": "E"}, {"name": "F"},
    ]
    days = build_day_plan("2026-08-18", 3, weather, attractions)

    assert len(days) == 3
    assert days[0]["day"] == 1
    assert days[0]["date"] == "2026-08-18"
    assert days[0]["weather"] == "晴 21~31°C"
    assert len(days[0]["attractions"]) == 2


def test_select_skill_weather_forecast():
    assert agent_router._select_skill(
        IntentType.WEATHER_QUERY, "北京未来三天天气怎么样", {"destination": "北京"}
    ) == "get_forecast"
    assert agent_router._select_skill(
        IntentType.WEATHER_QUERY, "北京明天天气", {"destination": "北京"}
    ) == "get_forecast"


def test_select_skill_weather_current():
    assert agent_router._select_skill(
        IntentType.WEATHER_QUERY, "北京天气怎么样", {"destination": "北京"}
    ) == "get_current_weather"


def test_select_skill_flight_detail():
    assert agent_router._select_skill(
        IntentType.FLIGHT_BOOKING, "CA1234这个航班怎么样", {}
    ) == "get_flight_detail"
    assert agent_router._select_skill(
        IntentType.FLIGHT_BOOKING, "查一下北京到上海的机票", {}
    ) == "search_flights"


def test_select_skill_hotel_attractions():
    assert agent_router._select_skill(
        IntentType.HOTEL_BOOKING, "北京有什么好玩的景点", {}
    ) == "search_attractions"
    assert agent_router._select_skill(
        IntentType.HOTEL_BOOKING, "北京有什么酒店推荐", {}
    ) == "search_hotels"
