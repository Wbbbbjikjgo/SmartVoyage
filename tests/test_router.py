"""Tests for the agent router (routing logic, no LLM / external network)."""

import pytest

from models.schemas import IntentType, IntentResult
from orchestrator.router import agent_router


@pytest.mark.asyncio
async def test_route_weather(monkeypatch):
    """Verify weather intent routes to the weather agent with location mapping."""
    captured = {}

    async def fake_recognize(user_input):
        return IntentResult(
            intent=IntentType.WEATHER_QUERY,
            confidence=0.9,
            slots={"destination": "北京"},
        )

    async def fake_invoke(agent, skill, params):
        captured["agent"] = agent
        captured["skill"] = skill
        captured["params"] = params
        return {"success": True, "data": {"location": "北京", "source": "mock"}}

    monkeypatch.setattr(agent_router.intent_recognizer, "recognize_with_fallback", fake_recognize)
    monkeypatch.setattr(agent_router.network, "invoke_agent", fake_invoke)

    result = await agent_router.route("北京天气怎么样")

    assert result["agent"] == "weather"
    assert captured["skill"] == "get_current_weather"
    assert captured["params"]["location"] == "北京"


@pytest.mark.asyncio
async def test_route_train(monkeypatch):
    """Verify train intent maps slots (departure->start, destination->end)."""
    captured = {}

    async def fake_recognize(user_input):
        return IntentResult(
            intent=IntentType.TRAIN_BOOKING,
            confidence=0.9,
            slots={"departure": "杭州", "destination": "北京"},
        )

    async def fake_invoke(agent, skill, params):
        captured["agent"] = agent
        captured["skill"] = skill
        captured["params"] = params
        return {"success": True, "data": {"trains": [], "total": 0}}

    monkeypatch.setattr(agent_router.intent_recognizer, "recognize_with_fallback", fake_recognize)
    monkeypatch.setattr(agent_router.network, "invoke_agent", fake_invoke)

    result = await agent_router.route("杭州到北京的高铁")

    assert result["agent"] == "train"
    assert captured["skill"] == "search_trains"
    assert captured["params"]["start"] == "杭州"
    assert captured["params"]["end"] == "北京"
    # 日期默认填充为「明天」
    assert "date" in captured["params"]


@pytest.mark.asyncio
async def test_route_missing_slots(monkeypatch):
    """Verify missing required slots produce a follow-up prompt."""
    async def fake_recognize(user_input):
        return IntentResult(
            intent=IntentType.TRAIN_BOOKING,
            confidence=0.9,
            slots={},
        )

    async def fake_invoke(agent, skill, params):
        raise AssertionError("should not be invoked when slots are missing")

    monkeypatch.setattr(agent_router.intent_recognizer, "recognize_with_fallback", fake_recognize)
    monkeypatch.setattr(agent_router.network, "invoke_agent", fake_invoke)

    result = await agent_router.route("帮我订个车票")

    assert result["success"] is True
    assert "missing_slots" in result


def test_prepare_parameters_flight_default_date():
    params = agent_router._prepare_parameters(
        "flight",
        "search_flights",
        {"departure": "北京", "destination": "上海"},
    )
    assert params["departure"] == "北京"
    assert params["arrival"] == "上海"
    assert "date" in params  # 默认明天


def test_prepare_parameters_hotel_checkout():
    params = agent_router._prepare_parameters(
        "hotel",
        "search_hotels",
        {"destination": "北京", "date": "2026-08-20", "duration": 3},
    )
    assert params["location"] == "北京"
    assert params["check_in"] == "2026-08-20"
    assert params["check_out"] == "2026-08-23"
