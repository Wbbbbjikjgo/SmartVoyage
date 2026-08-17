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


@pytest.mark.asyncio
async def test_search_attractions_mock():
    server = HotelMCPServer(mock_mode=True)
    result = await server.search_attractions("北京", limit=6)
    await server.close()
    assert result["source"] == "mock"
    assert 1 <= len(result["attractions"]) <= 6
    assert result["attractions"][0]["name"]


def test_flight_normalize_real_shape():
    """回归测试：按聚合数据航班接口的真实返回结构做字段归一化。"""
    from mcp_servers.flight_mcp import _extract_list, _normalize_flight_item

    raw = {
        "reason": "成功",
        "result": {
            "orderid": "JH0001",
            "flightInfo": [
                {
                    "airline": "MU",
                    "airlineName": "中国东方航空公司",
                    "flightNo": "MU5100",
                    "isCodeShare": False,
                    "equipment": "32N",
                    "departure": "PEK",
                    "departureName": "首都国际机场",
                    "departureDate": "2026-09-01",
                    "departureTime": "07:00",
                    "arrival": "PVG",
                    "arrivalName": "浦东国际机场",
                    "arrivalDate": "2026-09-01",
                    "arrivalTime": "08:55",
                    "duration": "01h55m",
                    "transferNum": 1,
                    "ticketPrice": 719,
                    "segments": [],
                }
            ],
        },
        "error_code": 0,
    }

    items = _extract_list(raw)
    assert len(items) == 1

    flight = _normalize_flight_item(items[0], "北京", "上海")
    assert flight["flight_no"] == "MU5100"
    assert flight["airline"] == "中国东方航空公司"
    assert flight["airline_code"] == "MU"
    assert flight["departure"] == "北京"
    assert flight["arrival"] == "上海"
    assert flight["departure_airport"] == "PEK"
    assert flight["departure_airport_name"] == "首都国际机场"
    assert flight["arrival_airport"] == "PVG"
    assert flight["departure_time"] == "07:00"
    assert flight["arrival_time"] == "08:55"
    assert flight["aircraft"] == "32N"
    assert flight["segments"] == 1
    assert flight["stops"] == 0  # transferNum=1 表示直飞，经停 0 次
    assert flight["price"] == 719


def test_train_normalize_real_shape():
    """回归测试：按极速数据火车票接口的真实返回结构做字段归一化。"""
    from mcp_servers.train_mcp import _normalize_train_item

    raw_item = {
        "trainno": "K2907",
        "type": "K",
        "typename": "快速",
        "station": "商丘",
        "endstation": "洛阳",
        "departuretime": "00:07",
        "arrivaltime": "04:57",
        "costtime": "4小时50分",
        "day": 1,
        "priceyw": 96.5,
        "priceyw1": 96.5,
        "priceyw2": 101.5,
        "priceyw3": 104.5,
        "priceyz": 50.5,
        "pricewz": 50.5,
        "pricerz": "-",
        "pricerw": "-",
        "pricesw": "-",
    }

    train = _normalize_train_item(raw_item, "商丘", "洛阳")
    assert train["train_no"] == "K2907"
    assert train["train_type"] == "快速"
    assert train["departure_station"] == "商丘"
    assert train["arrival_station"] == "洛阳"
    assert train["departure_time"] == "00:07"
    assert train["arrival_time"] == "04:57"
    assert train["duration"] == "4小时50分"
    assert train["seats"]["硬座"] == 50.5
    assert train["seats"]["硬卧"] == 96.5
    assert train["seats"]["无座"] == 50.5
    assert train["price"] == 50.5  # K 字头无二等座，取无座价
