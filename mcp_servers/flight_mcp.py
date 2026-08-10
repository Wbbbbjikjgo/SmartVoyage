"""Flight MCP tool server with mock data."""

import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta
import random

logger = logging.getLogger(__name__)


class FlightMCPServer:
    """MCP server for flight-related tools using mock data."""

    def __init__(self):
        """Initialize flight MCP server."""
        self.name = "Flight Tools"
        self.description = "航班查询工具集（模拟数据）"

        # Mock airline data
        self.airlines = {
            "CA": "中国国际航空",
            "MU": "中国东方航空",
            "CZ": "中国南方航空",
            "HU": "海南航空",
            "3U": "四川航空",
            "ZH": "深圳航空",
            "MF": "厦门航空",
            "SC": "山东航空",
            "9C": "春秋航空",
            "GS": "天津航空",
            "KN": "中国联合航空",
            "QW": "青岛航空",
            "DR": "瑞丽航空",
            "8L": "祥鹏航空",
        }

        # Aircraft types for richer mock data
        self.aircraft_types = [
            "Boeing 737-800", "Boeing 737 MAX 8", "Boeing 787-9",
            "Airbus A320", "Airbus A321neo", "Airbus A330-300",
            "Airbus A350-900", "COMAC C919", "COMAC ARJ21",
        ]

        # Mock city airport codes
        self.city_airports = {
            "北京": "PEK",
            "上海": "PVG",
            "广州": "CAN",
            "深圳": "SZX",
            "成都": "CTU",
            "杭州": "HGH",
            "西安": "XIY",
            "重庆": "CKG",
            "武汉": "WUH",
            "南京": "NKG",
            "天津": "TSN",
            "长沙": "CSX",
            "青岛": "TAO",
            "大连": "DLC",
            "厦门": "XMN",
            "昆明": "KMG",
            "三亚": "SYX",
            "海口": "HAK",
        }

    async def search_flights(
        self,
        departure: str,
        arrival: str,
        date: str,
        passengers: int = 1,
    ) -> Dict[str, Any]:
        """
        Search for available flights.

        Args:
            departure: Departure city
            arrival: Arrival city
            date: Travel date (YYYY-MM-DD)
            passengers: Number of passengers

        Returns:
            List of available flights
        """
        try:
            # Validate cities
            if departure not in self.city_airports:
                return {
                    "error": True,
                    "message": f"不支持的出发城市: {departure}",
                }
            if arrival not in self.city_airports:
                return {
                    "error": True,
                    "message": f"不支持的到达城市: {arrival}",
                }

            dep_code = self.city_airports[departure]
            arr_code = self.city_airports[arrival]

            # Beijing has two airports
            dep_code_display = dep_code
            arr_code_display = arr_code

            # Generate mock flights (10-14 flights per route for richer results)
            num_flights = random.randint(10, 14)
            flights = []

            for i in range(num_flights):
                airline_code = random.choice(list(self.airlines.keys()))
                airline_name = self.airlines[airline_code]
                flight_no = f"{airline_code}{random.randint(1000, 9999)}"

                # Generate random departure time (6:00 - 22:00)
                dep_hour = random.randint(6, 22)
                dep_minute = random.choice([0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55])
                departure_time = f"{dep_hour:02d}:{dep_minute:02d}"

                # Flight duration: 1-4 hours
                duration_hours = random.randint(1, 4)
                duration_minutes = random.randint(0, 59)
                total_dep = dep_hour * 60 + dep_minute
                total_arr = total_dep + duration_hours * 60 + duration_minutes
                arr_hour = (total_arr // 60) % 24
                arr_minute = total_arr % 60
                arrival_time = f"{arr_hour:02d}:{arr_minute:02d}"

                # Price: 400-3200 CNY
                price = random.randint(4, 32) * 100

                # Beijing second airport variation
                flight_dep_code = dep_code_display
                flight_arr_code = arr_code_display
                if departure == "北京" and random.random() < 0.4:
                    flight_dep_code = "PKX"
                if arrival == "北京" and random.random() < 0.4:
                    flight_arr_code = "PKX"

                flights.append({
                    "flight_no": flight_no,
                    "airline": airline_name,
                    "departure": departure,
                    "arrival": arrival,
                    "departure_airport": flight_dep_code,
                    "arrival_airport": flight_arr_code,
                    "departure_time": departure_time,
                    "arrival_time": arrival_time,
                    "duration": f"{duration_hours}h {duration_minutes}m",
                    "aircraft": random.choice(self.aircraft_types),
                    "on_time_rate": f"{random.randint(70, 98)}%",
                    "meal": random.choice(["有餐食", "无餐食", "轻食"]),
                    "stops": 0,
                    "discount": f"{random.randint(3, 9)}.{random.randint(0, 9)}折",
                    "price": price,
                    "currency": "CNY",
                    "available_seats": random.randint(3, 200),
                    "date": date,
                })

            # Sort by departure time
            flights.sort(key=lambda x: x["departure_time"])

            return {
                "departure": departure,
                "arrival": arrival,
                "date": date,
                "passengers": passengers,
                "flights": flights,
                "total": len(flights),
            }

        except Exception as e:
            logger.exception(f"Error searching flights: {e}")
            return {"error": True, "message": str(e)}

    async def get_flight_detail(self, flight_no: str, date: str) -> Dict[str, Any]:
        """
        Get detailed information for a specific flight.

        Args:
            flight_no: Flight number (e.g., CA1234)
            date: Flight date

        Returns:
            Flight detail dictionary
        """
        try:
            # Extract airline code
            airline_code = flight_no[:2]
            if airline_code not in self.airlines:
                return {"error": True, "message": f"无效的航班号: {flight_no}"}

            airline_name = self.airlines[airline_code]

            # Mock flight detail
            return {
                "flight_no": flight_no,
                "airline": airline_name,
                "aircraft": "Boeing 737-800",
                "departure_airport": "PEK",
                "arrival_airport": "PVG",
                "departure_time": "08:30",
                "arrival_time": "10:45",
                "duration": "2h 15m",
                "meal": "有",
                "on_time_rate": "85%",
                "date": date,
            }

        except Exception as e:
            logger.exception(f"Error getting flight detail: {e}")
            return {"error": True, "message": str(e)}

    def get_tools(self) -> list:
        """Get list of available tools."""
        return [
            {
                "name": "search_flights",
                "description": "搜索可用航班",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "departure": {
                            "type": "string",
                            "description": "出发城市（如：北京）",
                        },
                        "arrival": {
                            "type": "string",
                            "description": "到达城市（如：上海）",
                        },
                        "date": {
                            "type": "string",
                            "description": "出行日期（YYYY-MM-DD）",
                        },
                        "passengers": {
                            "type": "integer",
                            "description": "乘客人数",
                            "default": 1,
                        },
                    },
                    "required": ["departure", "arrival", "date"],
                },
            },
            {
                "name": "get_flight_detail",
                "description": "获取航班详细信息",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "flight_no": {
                            "type": "string",
                            "description": "航班号（如：CA1234）",
                        },
                        "date": {
                            "type": "string",
                            "description": "航班日期",
                        },
                    },
                    "required": ["flight_no", "date"],
                },
            },
        ]


# Global instance
flight_mcp = FlightMCPServer()
