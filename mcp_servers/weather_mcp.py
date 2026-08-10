"""Weather MCP tool server using QWeather API (with mock fallback)."""

import json
import logging
import random
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import httpx
from configs.settings import settings

logger = logging.getLogger(__name__)

# Weather condition pools for mock data
_MOCK_CONDITIONS = [
    ("晴", "100"), ("多云", "101"), ("阴", "104"),
    ("小雨", "305"), ("中雨", "306"), ("雷阵雨", "302"),
]


def _mock_current_weather(location: str) -> Dict[str, Any]:
    """Generate mock current weather data."""
    text, icon = random.choice(_MOCK_CONDITIONS)
    return {
        "location": location,
        "temperature": round(random.uniform(5, 35), 1),
        "description": text,
        "humidity": random.randint(30, 90),
        "wind_speed": round(random.uniform(1, 30), 1),
        "wind_direction": random.choice(["北风", "东北风", "东风", "东南风", "南风", "西南风", "西风", "西北风"]),
        "icon": icon,
        "update_time": datetime.now().isoformat(),
        "mock": True,
    }


def _mock_forecast(location: str, days: int) -> Dict[str, Any]:
    """Generate mock forecast data."""
    forecasts = []
    today = datetime.now().date()
    for i in range(days):
        text_day, icon_day = random.choice(_MOCK_CONDITIONS)
        text_night, icon_night = random.choice(_MOCK_CONDITIONS)
        temp_min = round(random.uniform(0, 25), 1)
        forecasts.append({
            "date": (today + timedelta(days=i)).isoformat(),
            "temp_max": round(temp_min + random.uniform(5, 12), 1),
            "temp_min": temp_min,
            "description_day": text_day,
            "description_night": text_night,
            "humidity": random.randint(30, 90),
            "wind_speed": round(random.uniform(1, 30), 1),
            "icon_day": icon_day,
            "icon_night": icon_night,
        })
    return {
        "location": location,
        "forecast": forecasts,
        "update_time": datetime.now().isoformat(),
        "mock": True,
    }


def _mock_air_quality(location: str) -> Dict[str, Any]:
    """Generate mock air quality data."""
    aqi = random.randint(20, 150)
    if aqi <= 50:
        level, category = "1", "优"
    elif aqi <= 100:
        level, category = "2", "良"
    else:
        level, category = "3", "轻度污染"
    return {
        "location": location,
        "aqi": aqi,
        "level": level,
        "category": category,
        "pm10": round(random.uniform(10, 120), 1),
        "pm2p5": round(random.uniform(5, 80), 1),
        "no2": round(random.uniform(5, 60), 1),
        "so2": round(random.uniform(2, 30), 1),
        "o3": round(random.uniform(20, 150), 1),
        "co": round(random.uniform(0.3, 1.5), 2),
        "update_time": datetime.now().isoformat(),
        "mock": True,
    }


class WeatherMCPServer:
    """MCP server for weather-related tools using QWeather API."""

    def __init__(self):
        """Initialize weather MCP server."""
        self.api_key = settings.qweather_api_key
        self.base_url = settings.qweather_base_url
        self.mock_mode = settings.qweather_mock_mode
        self.name = "Weather Tools"
        self.description = "天气查询工具集"

    async def get_current_weather(self, location: str) -> Dict[str, Any]:
        """
        Get current weather for a location.

        Args:
            location: City name (Chinese or English)

        Returns:
            Weather data dictionary
        """
        if self.mock_mode:
            return _mock_current_weather(location)
        try:
            # First, get location ID using GeoAPI
            geo_url = f"{self.base_url}/v7/geo/v2/city/lookup"
            geo_params = {
                "location": location,
                "key": self.api_key,
            }

            async with httpx.AsyncClient() as client:
                geo_response = await client.get(geo_url, params=geo_params)
                geo_data = geo_response.json()

                if geo_data.get("code") != "200":
                    logger.error(f"GeoAPI error: {geo_data}")
                    return {"error": True, "message": f"Location not found: {location}"}

                # Get the first matching location
                location_data = geo_data["location"][0]
                location_id = location_data["id"]
                location_name = location_data["name"]

                # Now get current weather
                weather_url = f"{self.base_url}/v7/weather/now"
                weather_params = {
                    "location": location_id,
                    "key": self.api_key,
                }

                weather_response = await client.get(weather_url, params=weather_params)
                weather_data = weather_response.json()

                if weather_data.get("code") != "200":
                    logger.error(f"Weather API error: {weather_data}")
                    return {"error": True, "message": "Failed to get weather data"}

                now = weather_data["now"]

                return {
                    "location": location_name,
                    "temperature": float(now["temp"]),
                    "description": now["text"],
                    "humidity": int(now["humidity"]),
                    "wind_speed": float(now["windSpeed"]),
                    "wind_direction": now["windDir"],
                    "icon": now["icon"],
                    "update_time": weather_data["updateTime"],
                }

        except Exception as e:
            logger.exception(f"Error getting weather data: {e}")
            # Fallback to mock data on API failure
            logger.warning("Falling back to mock weather data")
            return _mock_current_weather(location)

    async def get_forecast(self, location: str, days: int = 3) -> Dict[str, Any]:
        """
        Get weather forecast for a location.

        Args:
            location: City name
            days: Number of forecast days (3 or 7)

        Returns:
            Forecast data dictionary
        """
        if self.mock_mode:
            return _mock_forecast(location, days)
        try:
            # Get location ID
            geo_url = f"{self.base_url}/v7/geo/v2/city/lookup"
            geo_params = {"location": location, "key": self.api_key}

            async with httpx.AsyncClient() as client:
                geo_response = await client.get(geo_url, params=geo_params)
                geo_data = geo_response.json()

                if geo_data.get("code") != "200":
                    return {"error": True, "message": f"Location not found: {location}"}

                location_id = geo_data["location"][0]["id"]
                location_name = geo_data["location"][0]["name"]

                # Get forecast
                forecast_url = f"{self.base_url}/v7/weather/{days}d"
                forecast_params = {"location": location_id, "key": self.api_key}

                forecast_response = await client.get(forecast_url, params=forecast_params)
                forecast_data = forecast_response.json()

                if forecast_data.get("code") != "200":
                    return {"error": True, "message": "Failed to get forecast data"}

                daily_forecasts = []
                for day in forecast_data["daily"]:
                    daily_forecasts.append({
                        "date": day["fxDate"],
                        "temp_max": float(day["tempMax"]),
                        "temp_min": float(day["tempMin"]),
                        "description_day": day["textDay"],
                        "description_night": day["textNight"],
                        "humidity": int(day["humidity"]),
                        "wind_speed": float(day["windSpeedDay"]),
                        "icon_day": day["iconDay"],
                        "icon_night": day["iconNight"],
                    })

                return {
                    "location": location_name,
                    "forecast": daily_forecasts,
                    "update_time": forecast_data["updateTime"],
                }

        except Exception as e:
            logger.exception(f"Error getting forecast: {e}")
            logger.warning("Falling back to mock forecast data")
            return _mock_forecast(location, days)

    async def get_air_quality(self, location: str) -> Dict[str, Any]:
        """
        Get air quality data for a location.

        Args:
            location: City name

        Returns:
            Air quality data dictionary
        """
        if self.mock_mode:
            return _mock_air_quality(location)
        try:
            # Get location ID
            geo_url = f"{self.base_url}/v7/geo/v2/city/lookup"
            geo_params = {"location": location, "key": self.api_key}

            async with httpx.AsyncClient() as client:
                geo_response = await client.get(geo_url, params=geo_params)
                geo_data = geo_response.json()

                if geo_data.get("code") != "200":
                    return {"error": True, "message": f"Location not found: {location}"}

                location_id = geo_data["location"][0]["id"]
                location_name = geo_data["location"][0]["name"]

                # Get air quality
                air_url = f"{self.base_url}/v7/air/now"
                air_params = {"location": location_id, "key": self.api_key}

                air_response = await client.get(air_url, params=air_params)
                air_data = air_response.json()

                if air_data.get("code") != "200":
                    return {"error": True, "message": "Failed to get air quality data"}

                now = air_data["now"]

                return {
                    "location": location_name,
                    "aqi": int(now["aqi"]),
                    "level": now["level"],
                    "category": now["category"],
                    "pm10": float(now["pm10"]),
                    "pm2p5": float(now["pm2p5"]),
                    "no2": float(now["no2"]),
                    "so2": float(now["so2"]),
                    "o3": float(now["o3"]),
                    "co": float(now["co"]),
                    "update_time": air_data["updateTime"],
                }

        except Exception as e:
            logger.exception(f"Error getting air quality: {e}")
            logger.warning("Falling back to mock air quality data")
            return _mock_air_quality(location)

    def get_tools(self) -> list:
        """Get list of available tools."""
        return [
            {
                "name": "get_current_weather",
                "description": "获取指定城市的当前天气",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "城市名称（中文或英文）",
                        }
                    },
                    "required": ["location"],
                },
            },
            {
                "name": "get_forecast",
                "description": "获取指定城市的天气预报",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "城市名称",
                        },
                        "days": {
                            "type": "integer",
                            "description": "预报天数（3或7）",
                            "default": 3,
                        },
                    },
                    "required": ["location"],
                },
            },
            {
                "name": "get_air_quality",
                "description": "获取指定城市的空气质量数据",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "城市名称",
                        }
                    },
                    "required": ["location"],
                },
            },
        ]


# Global instance
weather_mcp = WeatherMCPServer()
