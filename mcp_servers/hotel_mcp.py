"""Hotel MCP tool server with mock data."""

import logging
from typing import Dict, Any, List
import random

logger = logging.getLogger(__name__)


class HotelMCPServer:
    """MCP server for hotel-related tools using mock data."""

    def __init__(self):
        """Initialize hotel MCP server."""
        self.name = "Hotel Tools"
        self.description = "酒店查询工具集（模拟数据）"

        # Mock hotel chains
        self.hotel_chains = [
            "如家酒店",
            "汉庭酒店",
            "锦江之星",
            "7天连锁",
            "希尔顿酒店",
            "万豪酒店",
            "洲际酒店",
            "香格里拉酒店",
            "皇冠假日酒店",
            "假日酒店",
        ]

        # Mock amenities
        self.amenities_list = [
            "免费WiFi",
            "停车场",
            "早餐",
            "健身房",
            "游泳池",
            "SPA",
            "餐厅",
            "会议室",
            "洗衣服务",
            "叫醒服务",
            "行李寄存",
            "前台24小时",
        ]

        # Mock city districts
        self.city_districts = {
            "北京": ["朝阳区", "海淀区", "东城区", "西城区", "丰台区", "通州区"],
            "上海": ["浦东新区", "黄浦区", "静安区", "徐汇区", "长宁区", "虹口区"],
            "广州": ["天河区", "越秀区", "海珠区", "荔湾区", "白云区", "番禺区"],
            "深圳": ["福田区", "罗湖区", "南山区", "宝安区", "龙岗区", "龙华区"],
            "成都": ["锦江区", "青羊区", "武侯区", "成华区", "高新区", "天府新区"],
            "杭州": ["上城区", "下城区", "西湖区", "拱墅区", "滨江区", "余杭区"],
            "西安": ["雁塔区", "碑林区", "莲湖区", "未央区", "灞桥区", "长安区"],
            "重庆": ["渝中区", "江北区", "南岸区", "沙坪坝区", "九龙坡区", "渝北区"],
        }

    async def search_hotels(
        self,
        location: str,
        check_in: str,
        check_out: str,
        guests: int = 2,
        price_range: str = None,
    ) -> Dict[str, Any]:
        """
        Search for available hotels.

        Args:
            location: City name
            check_in: Check-in date (YYYY-MM-DD)
            check_out: Check-out date (YYYY-MM-DD)
            guests: Number of guests
            price_range: Price range (e.g., "200-500")

        Returns:
            List of available hotels
        """
        try:
            # Get districts for the city
            districts = self.city_districts.get(location, ["市中心"])

            # Generate mock hotels (8-12 hotels)
            num_hotels = random.randint(8, 12)
            hotels = []

            for i in range(num_hotels):
                chain = random.choice(self.hotel_chains)
                district = random.choice(districts)
                hotel_name = f"{chain}({location}{district}店)"

                # Price: 150-1500 CNY per night
                if price_range:
                    min_price, max_price = map(int, price_range.split("-"))
                    price = random.randint(min_price, max_price)
                else:
                    price = random.randint(15, 150) * 10

                # Rating: 3.5-5.0
                rating = round(random.uniform(3.5, 5.0), 1)

                # Random amenities (4-8 items)
                num_amenities = random.randint(4, 8)
                amenities = random.sample(self.amenities_list, num_amenities)

                hotels.append({
                    "hotel_name": hotel_name,
                    "location": f"{location} {district}",
                    "address": f"{district}某某路{random.randint(1, 999)}号",
                    "price_per_night": price,
                    "currency": "CNY",
                    "rating": rating,
                    "review_count": random.randint(100, 5000),
                    "amenities": amenities,
                    "room_types": ["标准间", "大床房", "套房"][:random.randint(1, 3)],
                    "available_rooms": random.randint(5, 50),
                })

            # Sort by rating (descending)
            hotels.sort(key=lambda x: x["rating"], reverse=True)

            return {
                "location": location,
                "check_in": check_in,
                "check_out": check_out,
                "guests": guests,
                "hotels": hotels,
                "total": len(hotels),
            }

        except Exception as e:
            logger.exception(f"Error searching hotels: {e}")
            return {"error": True, "message": str(e)}

    async def get_hotel_detail(self, hotel_name: str, date: str) -> Dict[str, Any]:
        """
        Get detailed information for a specific hotel.

        Args:
            hotel_name: Hotel name
            date: Check-in date

        Returns:
            Hotel detail dictionary
        """
        try:
            # Mock hotel detail
            return {
                "hotel_name": hotel_name,
                "description": "这是一家舒适的酒店，提供优质的住宿体验。",
                "address": "某某路123号",
                "phone": "010-12345678",
                "check_in_time": "14:00",
                "check_out_time": "12:00",
                "room_types": [
                    {
                        "type": "标准间",
                        "price": 399,
                        "bed": "双床",
                        "area": "25㎡",
                        "breakfast": "不含早",
                    },
                    {
                        "type": "大床房",
                        "price": 459,
                        "bed": "大床",
                        "area": "28㎡",
                        "breakfast": "含单早",
                    },
                    {
                        "type": "豪华套房",
                        "price": 899,
                        "bed": "大床",
                        "area": "45㎡",
                        "breakfast": "含双早",
                    },
                ],
                "amenities": self.amenities_list[:8],
                "policies": {
                    "cancellation": "入住前24小时可免费取消",
                    "children": "12岁以下儿童免费加床",
                    "pets": "不允许携带宠物",
                },
                "date": date,
            }

        except Exception as e:
            logger.exception(f"Error getting hotel detail: {e}")
            return {"error": True, "message": str(e)}

    def get_tools(self) -> list:
        """Get list of available tools."""
        return [
            {
                "name": "search_hotels",
                "description": "搜索可用酒店",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "城市名称（如：北京）",
                        },
                        "check_in": {
                            "type": "string",
                            "description": "入住日期（YYYY-MM-DD）",
                        },
                        "check_out": {
                            "type": "string",
                            "description": "退房日期（YYYY-MM-DD）",
                        },
                        "guests": {
                            "type": "integer",
                            "description": "入住人数",
                            "default": 2,
                        },
                        "price_range": {
                            "type": "string",
                            "description": "价格范围（如：200-500）",
                        },
                    },
                    "required": ["location", "check_in", "check_out"],
                },
            },
            {
                "name": "get_hotel_detail",
                "description": "获取酒店详细信息",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "hotel_name": {
                            "type": "string",
                            "description": "酒店名称",
                        },
                        "date": {
                            "type": "string",
                            "description": "入住日期",
                        },
                    },
                    "required": ["hotel_name", "date"],
                },
            },
        ]


# Global instance
hotel_mcp = HotelMCPServer()
