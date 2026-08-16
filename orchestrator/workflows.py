"""
多 Agent 协同工作流定义 - 旅行规划工作流

核心功能：协调多个 Agent 协作完成一个完整的旅行规划任务
工作流程：查天气 → 查机票 → 查酒店 → 创建行程 → 添加预订
"""

import logging
from typing import Dict, Any, Optional
from datetime import date, timedelta
from orchestrator.agent_network import agent_network

# 获取日志记录器
logger = logging.getLogger(__name__)


# ================================================================
# 1. 旅行规划工作流类
# ================================================================

class TravelPlanningWorkflow:
    """
    旅行规划工作流

    作用：把多个 Agent 串起来，完成一个完整的旅行规划
    涉及 Agent：
        1. weather Agent - 查询目的地天气
        2. flight Agent - 搜索机票
        3. hotel Agent - 搜索酒店
        4. itinerary Agent - 创建行程和预订

    流程：天气 → 机票 → 酒店 → 创建行程 → 添加预订
    """

    def __init__(self):
        """初始化工作流，引用 Agent 网络"""
        # agent_network：管理所有 Agent 的注册和调用
        self.network = agent_network

    # ================================================================
    # 2. 工具方法：解包 Agent 返回结果
    # ================================================================

    @staticmethod
    def _unwrap(result: Dict[str, Any]) -> Dict[str, Any]:
        """
        解包 Agent 技能调用结果

        问题：Agent 返回的格式是 {"success": True, "data": {...}}
        但我们真正想要的是 data 里面的内容

        这个方法把外面的壳剥掉，直接返回内部数据

        示例：
            输入: {"success": True, "data": {"flights": [...]}}
            输出: {"flights": [...]}

            输入: {"error": True, "message": "出错了"}
            输出: {"error": True, "message": "出错了"}  # 错误情况直接返回

        Args:
            result: Agent 返回的原始结果

        Returns:
            解包后的数据
        """
        # 如果有错误标记，直接返回（不要解包）
        if result.get("error"):
            return result
        # 如果成功且有 data 字段且 data 是字典，返回 data
        if result.get("success") and isinstance(result.get("data"), dict):
            return result["data"]
        # 其他情况直接返回原结果
        return result

    # ================================================================
    # 3. 主要方法：执行完整旅行规划
    # ================================================================

    async def execute(
        self,
        user_id: int,               # 用户ID
        destination: str,           # 目的地城市（如 "北京"）
        start_date: str,            # 开始日期（如 "2024-08-20"）
        duration: int,              # 持续天数（如 3）
        departure: str = None,      # 出发城市（可选，如 "上海"）
        budget: float = None,       # 预算（可选）
        guests: int = 1,            # 人数（默认1人）
    ) -> Dict[str, Any]:
        """
        执行完整的旅行规划工作流

        流程：
            1. 查询目的地天气
            2. 搜索机票（如果提供了出发城市）
            3. 搜索酒店
            4. 创建行程
            5. 添加机票预订（如果有航班）
            6. 添加酒店预订（如果有酒店）

        Args:
            user_id: 用户ID
            destination: 目的地
            start_date: 开始日期
            duration: 持续天数
            departure: 出发城市（可选）
            budget: 预算（可选）
            guests: 人数

        Returns:
            完整的行程结果，包含天气、航班、酒店、预订信息
        """
        # -------- 准备结果容器 --------
        result = {
            "destination": destination,      # 目的地
            "start_date": start_date,        # 开始日期
            "duration": duration,            # 持续天数
            "steps": [],                     # 记录每一步的执行结果
        }

        try:
            # ============================================================
            # 步骤1：查询天气
            # ============================================================
            logger.info(f"步骤1: 查询 {destination} 的天气")
            weather_result = await self.network.invoke_agent(
                "weather",                    # Agent 名称
                "get_forecast",               # 技能名称：获取天气预报
                {
                    "location": destination,
                    "days": duration,          # 查询未来几天的天气
                },
            )
            # 解包结果
            weather_result = self._unwrap(weather_result)
            # 记录执行步骤
            result["steps"].append({
                "step": "weather",                                     # 步骤名称
                "status": "success" if not weather_result.get("error") else "error",
                "data": weather_result,                                # 步骤数据
            })
            result["weather"] = weather_result  # 存到结果中

            # ============================================================
            # 步骤2：搜索航班（只有用户提供了出发城市才执行）
            # ============================================================
            if departure:
                logger.info(f"步骤2: 搜索从 {departure} 到 {destination} 的航班")
                flight_result = await self.network.invoke_agent(
                    "flight",                    # Agent 名称
                    "search_flights",            # 技能名称：搜索航班
                    {
                        "departure": departure,
                        "arrival": destination,
                        "date": start_date,
                        "passengers": guests,
                    },
                )
                flight_result = self._unwrap(flight_result)
                result["steps"].append({
                    "step": "flights",
                    "status": "success" if not flight_result.get("error") else "error",
                    "data": flight_result,
                })
                result["flights"] = flight_result

            # ============================================================
            # 步骤3：搜索酒店
            # ============================================================
            # 计算退房日期：入住日期 + 入住天数
            # 例如：8月20日入住，住3天，8月23日退房
            start = date.fromisoformat(start_date)           # 将日期字符串转为 date 对象
            check_out = start + timedelta(days=duration)     # 计算退房日期
            check_out_str = check_out.isoformat()            # 转回字符串

            logger.info(f"步骤3: 搜索 {destination} 的酒店")
            hotel_result = await self.network.invoke_agent(
                "hotel",                     # Agent 名称
                "search_hotels",             # 技能名称：搜索酒店
                {
                    "location": destination,
                    "check_in": start_date,
                    "check_out": check_out_str,
                    "guests": guests,
                },
            )
            hotel_result = self._unwrap(hotel_result)
            result["steps"].append({
                "step": "hotels",
                "status": "success" if not hotel_result.get("error") else "error",
                "data": hotel_result,
            })
            result["hotels"] = hotel_result

            # ============================================================
            # 步骤4：创建行程（写入数据库）
            # ============================================================
            logger.info(f"步骤4: 为用户 {user_id} 创建行程")
            itinerary_result = await self.network.invoke_agent(
                "itinerary",                 # Agent 名称
                "create_itinerary",          # 技能名称：创建行程
                {
                    "user_id": user_id,
                    "destination": destination,
                    "start_date": start_date,
                    "duration": duration,
                    "budget": budget,
                },
            )
            itinerary_result = self._unwrap(itinerary_result)
            result["steps"].append({
                "step": "create_itinerary",
                "status": "success" if not itinerary_result.get("error") else "error",
                "data": itinerary_result,
            })

            # ============================================================
            # 步骤5：添加机票预订（如果有航班）
            # ============================================================
            # 只有在创建行程成功、有出发城市、有航班数据、且航班无错误时才执行
            if not itinerary_result.get("error"):
                # 获取行程ID（创建行程后返回的）
                itinerary_id = itinerary_result["itinerary_id"]

                # 如果有出发城市、航班数据存在且无错误
                if departure and result.get("flights") and not result["flights"].get("error"):
                    flights = result["flights"].get("flights", [])
                    if flights:
                        # 选择第一个航班（最优航班）
                        selected_flight = flights[0]
                        
                        # 调用 itinerary Agent 添加机票预订
                        booking_result = await self.network.invoke_agent(
                            "itinerary",
                            "add_booking",          # 技能名称：添加预订
                            {
                                "itinerary_id": itinerary_id,
                                "booking_type": "flight",
                                "details": {
                                    "flight_no": selected_flight["flight_no"],
                                    "airline": selected_flight["airline"],
                                    "departure": selected_flight["departure"],
                                    "arrival": selected_flight["arrival"],
                                    "departure_time": selected_flight["departure_time"],
                                    "arrival_time": selected_flight["arrival_time"],
                                    "price": selected_flight["price"],
                                },
                            },
                        )
                        booking_result = self._unwrap(booking_result)
                        result["steps"].append({
                            "step": "book_flight",
                            "status": "success" if not booking_result.get("error") else "error",
                            "data": booking_result,
                        })

                # ============================================================
                # 步骤6：添加酒店预订（如果有酒店）
                # ============================================================
                if result.get("hotels") and not result["hotels"].get("error"):
                    hotels = result["hotels"].get("hotels", [])
                    if hotels:
                        # 选择第一个酒店（最优酒店）
                        selected_hotel = hotels[0]
                        
                        # 调用 itinerary Agent 添加酒店预订
                        booking_result = await self.network.invoke_agent(
                            "itinerary",
                            "add_booking",
                            {
                                "itinerary_id": itinerary_id,
                                "booking_type": "hotel",
                                "details": {
                                    "hotel_name": selected_hotel["hotel_name"],
                                    "location": selected_hotel["location"],
                                    "price_per_night": selected_hotel["price_per_night"],
                                    "rating": selected_hotel["rating"],
                                },
                            },
                        )
                        booking_result = self._unwrap(booking_result)
                        result["steps"].append({
                            "step": "book_hotel",
                            "status": "success" if not booking_result.get("error") else "error",
                            "data": booking_result,
                        })

                # 把行程ID加到结果中
                result["itinerary_id"] = itinerary_id

            # 标记整体成功
            result["success"] = True

        except Exception as e:
            # 捕获任何异常，记录错误
            logger.exception(f"旅行规划工作流执行出错: {e}")
            result["success"] = False
            result["error"] = str(e)

        return result

    # ================================================================
    # 4. 简化工作流：只查天气
    # ================================================================

    async def get_weather_only(self, location: str) -> Dict[str, Any]:
        """
        只查询天气（简化版工作流）

        使用场景：用户只想查天气，不需要完整行程

        Args:
            location: 城市名

        Returns:
            天气数据
        """
        return await self.network.invoke_agent(
            "weather",
            "get_current_weather",       # 获取当前天气（不是预报）
            {"location": location},
        )

    # ================================================================
    # 5. 简化工作流：只查航班
    # ================================================================

    async def search_flights_only(
        self,
        departure: str,      # 出发城市
        arrival: str,        # 到达城市
        date: str,           # 日期
        passengers: int = 1, # 人数
    ) -> Dict[str, Any]:
        """
        只搜索航班（简化版工作流）

        使用场景：用户只想查航班，不需要完整行程

        Args:
            departure: 出发城市
            arrival: 到达城市
            date: 出行日期
            passengers: 人数

        Returns:
            航班搜索结果
        """
        return await self.network.invoke_agent(
            "flight",
            "search_flights",
            {
                "departure": departure,
                "arrival": arrival,
                "date": date,
                "passengers": passengers,
            },
        )

    # ================================================================
    # 6. 简化工作流：只查酒店
    # ================================================================

    async def search_hotels_only(
        self,
        location: str,       # 位置/城市
        check_in: str,       # 入住日期
        check_out: str,      # 退房日期
        guests: int = 2,     # 人数（默认2人）
    ) -> Dict[str, Any]:
        """
        只搜索酒店（简化版工作流）

        使用场景：用户只想查酒店，不需要完整行程

        Args:
            location: 城市名
            check_in: 入住日期
            check_out: 退房日期
            guests: 人数

        Returns:
            酒店搜索结果
        """
        return await self.network.invoke_agent(
            "hotel",
            "search_hotels",
            {
                "location": location,
                "check_in": check_in,
                "check_out": check_out,
                "guests": guests,
            },
        )

    # ================================================================
    # 7. 简化工作流：只查高铁/火车票
    # ================================================================

    async def search_trains_only(
        self,
        start: str,               # 出发城市/车站
        end: str,                 # 到达城市/车站
        date: str = "",           # 出行日期
        is_high_speed: int = 0,   # 是否仅高铁
    ) -> Dict[str, Any]:
        """
        只搜索高铁/火车票（简化版工作流）

        使用场景：用户只想查火车票，不需要完整行程

        Args:
            start: 出发城市/车站
            end: 到达城市/车站
            date: 出行日期
            is_high_speed: 是否仅高铁

        Returns:
            火车票搜索结果
        """
        return await self.network.invoke_agent(
            "train",
            "search_trains",
            {
                "start": start,
                "end": end,
                "date": date,
                "is_high_speed": is_high_speed,
            },
        )


# ================================================================
# 8. 全局单例实例
# ================================================================

# 创建全局工作流实例，供其他模块导入使用
travel_workflow = TravelPlanningWorkflow()