"""Tests for MCP tool servers in mock mode (no network calls).

这些测试统一使用 mock 模式，不会消耗真实 API 额度（尤其是航班/火车票
付费接口的免费调用次数）。
"""

import pytest

from mcp_servers.weather_mcp import WeatherMCPServer
from mcp_servers.flight_mcp import FlightMCPServer
from mcp_servers.train_mcp import TrainMCPServer
from mcp_servers.hotel_mcp import HotelMCPServer


@pytest.mark.asyncio
async def test_weather_current_mock():
    server = WeatherMCPServer(mock_mode=True)
    result = await server.get_current_weather("北京")
    await server.close()
    assert result["source"] == "mock"
    assert result["location"] == "北京"
    assert "temperature" in result


@pytest.mark.asyncio
async def test_weather_forecast_mock():
    server = WeatherMCPServer(mock_mode=True)
    result = await server.get_forecast("上海", days=3)
    await server.close()
    assert result["source"] == "mock"
    assert len(result["forecast"]) == 3


@pytest.mark.asyncio
async def test_flight_search_mock():
    server = FlightMCPServer(mock_mode=True)
    result = await server.search_flights("北京", "上海", "2026-08-20")
    await server.close()
    assert result["source"] == "mock"
    assert result["total"] >= 10
    flight = result["flights"][0]
    assert flight["flight_no"]
    assert flight["airline"]


@pytest.mark.asyncio
async def test_flight_unsupported_city():
    server = FlightMCPServer(mock_mode=True)
    result = await server.search_flights("火星", "上海", "2026-08-20")
    await server.close()
    assert result["error"] is True


@pytest.mark.asyncio
async def test_train_search_mock():
    server = TrainMCPServer(mock_mode=True)
    result = await server.search_trains("杭州", "北京", "2026-08-20", is_high_speed=1)
    await server.close()
    assert result["source"] == "mock"
    assert result["total"] >= 8
    train = result["trains"][0]
    assert train["train_no"]
    assert "二等座" in train["seats"]


@pytest.mark.asyncio
async def test_train_high_speed_only():
    server = TrainMCPServer(mock_mode=True)
    result = await server.search_trains("杭州", "北京", "", is_high_speed=1)
    await server.close()
    for train in result["trains"]:
        assert train["train_no"][0] in ("G", "D", "C")


@pytest.mark.asyncio
async def test_hotel_search_mock():
    server = HotelMCPServer(mock_mode=True)
    result = await server.search_hotels("北京")
    await server.close()
    assert result["source"] == "mock"
    assert result["total"] >= 10
    hotel = result["hotels"][0]
    assert hotel["hotel_name"]
    assert hotel["rating"] >= 3.5


@pytest.mark.asyncio
async def test_hotel_detail_mock():
    server = HotelMCPServer(mock_mode=True)
    result = await server.get_hotel_detail("希尔顿酒店")
    await server.close()
    assert result["source"] == "mock"
    assert result["hotel_name"] == "希尔顿酒店"
