"""Weather MCP tool server using QWeather API."""

import json
import logging
from typing import Dict, Any, Optional
import httpx
from configs.settings import settings

logger = logging.getLogger(__name__)


class WeatherMCPServer:
    """MCP server for weather-related tools using QWeather API."""

    def __init__(self):
        """Initialize weather MCP server."""
        self.api_key = settings.qweather_api_key
        self.base_url = settings.qweather_base_url
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
            return {"error": True, "message": str(e)}

    async def get_forecast(self, location: str, days: int = 3) -> Dict[str, Any]:
        """
        Get weather forecast for a location.

        Args:
            location: City name
            days: Number of forecast days (3 or 7)

        Returns:
            Forecast data dictionary
        """
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
            return {"error": True, "message": str(e)}

    async def get_air_quality(self, location: str) -> Dict[str, Any]:
        """
        Get air quality data for a location.

        Args:
            location: City name

        Returns:
            Air quality data dictionary
        """
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
            return {"error": True, "message": str(e)}

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
