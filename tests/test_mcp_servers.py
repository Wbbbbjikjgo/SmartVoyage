"""Tests for real MCP servers (no network calls).

覆盖：
- MCP Server 确实通过 ``@mcp.tool()`` 注册了工具；
- 缺少 API Key / 上游失败时返回明确错误（绝不返回模拟数据）；
- 上游真实返回结构 -> 内部字段的归一化逻辑。
"""

import httpx
import pytest

from mcp_servers.flight_mcp import FlightMCPServer, _extract_list, _normalize_flight_item
from mcp_servers.hotel_mcp import HotelMCPServer
from mcp_servers.train_mcp import TrainMCPServer, _normalize_train_item
from mcp_servers.weather_mcp import WeatherMCPServer


@pytest.mark.asyncio
async def test_weather_tools_registered():
    from mcp_servers.weather_mcp import mcp

    tools = await mcp.list_tools()
    assert {t.name for t in tools} == {"get_current_weather", "get_forecast"}


@pytest.mark.asyncio
async def test_flight_tools_registered():
    from mcp_servers.flight_mcp import mcp

    tools = await mcp.list_tools()
    assert {t.name for t in tools} == {"search_flights", "get_flight_detail"}


@pytest.mark.asyncio
async def test_hotel_tools_registered():
    from mcp_servers.hotel_mcp import mcp

    tools = await mcp.list_tools()
    assert {t.name for t in tools} == {
        "search_hotels",
        "get_hotel_detail",
        "search_attractions",
    }


@pytest.mark.asyncio
async def test_train_tools_registered():
    from mcp_servers.train_mcp import mcp

    tools = await mcp.list_tools()
    assert {t.name for t in tools} == {"search_trains"}


@pytest.mark.asyncio
async def test_db_tools_registered():
    from mcp_servers.db_mcp import mcp

    tools = await mcp.list_tools()
    assert "create_itinerary" in {t.name for t in tools}


@pytest.mark.asyncio
async def test_weather_missing_key_returns_error():
    server = WeatherMCPServer()
    server.api_key = ""
    result = await server.get_current_weather("北京")
    await server.close()
    assert result["error"] is True
    assert "AMAP_API_KEY" in result["message"]


@pytest.mark.asyncio
async def test_weather_upstream_failure_returns_error(monkeypatch):
    server = WeatherMCPServer()
    server.api_key = "fake-key"

    async def boom(*args, **kwargs):
        raise httpx.ConnectError("network down")

    monkeypatch.setattr(server, "get_json", boom)
    result = await server.get_current_weather("北京")
    await server.close()
    assert result["error"] is True
    assert "network down" in result["message"]
    assert result.get("source") != "mock"


@pytest.mark.asyncio
async def test_flight_missing_key_returns_error():
    server = FlightMCPServer()
    server.appcode = ""
    result = await server.search_flights("北京", "上海", "2026-08-20")
    await server.close()
    assert result["error"] is True
    assert "ALIYUN_APPCODE" in result["message"]


@pytest.mark.asyncio
async def test_train_missing_key_returns_error():
    server = TrainMCPServer()
    server.appcode = ""
    result = await server.search_trains("杭州", "北京", "2026-08-20")
    await server.close()
    assert result["error"] is True
    assert "ALIYUN_APPCODE" in result["message"]


@pytest.mark.asyncio
async def test_hotel_missing_key_returns_error():
    server = HotelMCPServer()
    server.api_key = ""
    result = await server.search_hotels("北京")
    await server.close()
    assert result["error"] is True
    assert "AMAP_API_KEY" in result["message"]


def test_flight_normalize_real_shape():
    """回归测试：按聚合数据航班接口的真实返回结构做字段归一化。"""
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


def test_hotel_does_not_fabricate_price_or_amenities():
    """高德 POI 不提供房价/设施时，字段必须为空而不是伪造。"""
    from mcp_servers.hotel_mcp import _normalize_hotel_item

    hotel = _normalize_hotel_item({
        "name": "测试酒店",
        "address": "某路 1 号",
        "cityname": "北京",
        "adname": "东城区",
        "biz_ext": {"rating": "4.8"},
        "location": "116.4,39.9",
    })
    assert hotel["hotel_name"] == "测试酒店"
    assert hotel["rating"] == 4.8
    assert hotel["price_per_night"] is None
    assert hotel["amenities"] == []
