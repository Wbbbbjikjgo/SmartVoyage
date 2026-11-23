"""Multi-Agent travel planning workflow.

主 Agent 依次通过 A2A HTTP 调用天气 / 酒店 / 航班 / 火车票 Agent，收集真实
数据后，把这些真实数据交给行程 Agent，由其大模型生成逐日计划并写入数据库。

所有 Agent 都运行在独立进程中，只能通过 URL 访问，不存在进程内直接调用。
"""

import logging
from typing import Any, Dict, List, Optional

from configs.settings import settings
from orchestrator.a2a_client import call_agent
from orchestrator.agent_directory import resolve_agent_url

logger = logging.getLogger(__name__)


class TravelPlanningWorkflow:
    """Coordinate multiple remote A2A agents to build a real trip plan."""

    async def _ask(self, agent_name: str, prompt: str) -> str:
        """Send a prompt to a remote agent and return its text answer."""
        url = await resolve_agent_url(agent_name)
        if not url:
            raise RuntimeError(f"未找到 Agent「{agent_name}」的 URL")
        return await call_agent(url, prompt, timeout=settings.a2a_timeout)

    async def _step(
        self,
        steps: List[Dict[str, Any]],
        agent_name: str,
        prompt: str,
        label: Optional[str] = None,
    ) -> str:
        """Execute one remote-agent step, recording success or explicit error."""
        step_name = label or agent_name
        try:
            answer = await self._ask(agent_name, prompt)
            steps.append({
                "step": step_name,
                "agent": agent_name,
                "status": "success",
                "answer": answer,
            })
            return answer
        except Exception as exc:  # noqa: BLE001
            logger.exception("旅行工作流步骤失败: %s", step_name)
            steps.append({
                "step": step_name,
                "agent": agent_name,
                "status": "error",
                "answer": str(exc),
            })
            return ""

    async def execute(
        self,
        user_id: int,
        destination: str,
        start_date: str,
        duration: int,
        departure: Optional[str] = None,
        budget: Optional[float] = None,
        guests: int = 1,
        user_input: str = "",
    ) -> Dict[str, Any]:
        """Run the full multi-agent planning workflow."""
        steps: List[Dict[str, Any]] = []
        forecast_days = max(1, min(int(duration or 1), 4))

        # 1. 天气 Agent —— 真实天气预报
        weather_text = await self._step(
            steps,
            "weather",
            f"请查询「{destination}」未来 {forecast_days} 天的真实天气预报。"
            f"请只使用工具返回的真实数据，不要编造。",
        )

        # 2. 酒店 Agent —— 真实酒店
        hotel_text = await self._step(
            steps,
            "hotel",
            f"请搜索「{destination}」的真实酒店（约 {max(duration * 3, 6)} 家），"
            f"入住人数 {guests} 人。请只使用工具返回的真实数据。",
            label="hotels",
        )

        # 3. 酒店 Agent —— 真实景点
        attraction_text = await self._step(
            steps,
            "hotel",
            f"请搜索「{destination}」的真实热门景点（约 {max(duration * 3, 6)} 个）。"
            f"请只使用工具返回的真实数据。",
            label="attractions",
        )

        # 4. 交通 Agent —— 仅在提供出发城市时查询
        flight_text = ""
        train_text = ""
        if departure:
            flight_text = await self._step(
                steps,
                "flight",
                f"请查询 {start_date} 从「{departure}」到「{destination}」的真实航班，"
                f"乘客 {guests} 人。请只使用工具返回的真实数据。",
                label="flights",
            )
            train_text = await self._step(
                steps,
                "train",
                f"请查询 {start_date} 从「{departure}」到「{destination}」的真实高铁/火车票。"
                f"请只使用工具返回的真实数据。",
                label="trains",
            )

        # 5. 行程 Agent —— 基于真实数据生成逐日计划并写入数据库
        budget_line = f"预算：{budget} 元" if budget else "预算：未指定"
        itinerary_prompt = (
            f"用户原始请求：{user_input or '规划一次旅行'}\n"
            f"行程参数：目的地={destination}，开始日期={start_date}，天数={duration}，"
            f"人数={guests}，出发地={departure or '未指定'}，{budget_line}，user_id={user_id}\n\n"
            "以下是其他 Agent 通过真实接口获取的数据（严禁编造或替换）：\n"
            f"【天气】\n{weather_text or '（天气数据不可用）'}\n\n"
            f"【酒店】\n{hotel_text or '（酒店数据不可用）'}\n\n"
            f"【景点】\n{attraction_text or '（景点数据不可用）'}\n\n"
            f"【航班】\n{flight_text or '（未查询或航班数据不可用）'}\n\n"
            f"【车次】\n{train_text or '（未查询或车次数据不可用）'}\n\n"
            f"请根据以上真实数据生成 {duration} 天逐日行程（每天包含时间段、景点、"
            "交通方式、天气提示）。生成后请调用 create_itinerary 工具把行程保存到数据库"
            f"（user_id={user_id}，destination={destination}，start_date={start_date}，"
            f"duration={duration}，budget={budget}）。"
            f"如果 get_user 显示 user_id={user_id} 不存在，请先调用 create_user 创建用户"
            f"（name=SmartVoyage 用户，email=user{user_id}@smartvoyage.local），"
            "再用返回的 user_id 创建行程。如果数据库写入失败，如实说明错误，"
            "但仍然完整输出行程。"
        )

        answer = await self._step(steps, "itinerary", itinerary_prompt)

        return {
            "success": bool(answer),
            "destination": destination,
            "start_date": start_date,
            "duration": duration,
            "departure": departure,
            "budget": budget,
            "guests": guests,
            "answer": answer or "行程 Agent 未返回结果，请检查该 Agent 服务与日志。",
            "steps": steps,
            "weather": weather_text,
            "hotels": hotel_text,
            "attractions": attraction_text,
            "flights": flight_text,
            "trains": train_text,
        }

    # ================================================================
    # 便捷方法
    # ================================================================

    async def get_weather_only(self, location: str) -> str:
        """Query only the weather agent."""
        return await self._ask("weather", f"请查询「{location}」的真实实况天气。")

    async def search_flights_only(
        self, departure: str, arrival: str, date: str, passengers: int = 1
    ) -> str:
        """Query only the flight agent."""
        return await self._ask(
            "flight",
            f"请查询 {date} 从「{departure}」到「{arrival}」的真实航班，乘客 {passengers} 人。",
        )

    async def search_hotels_only(
        self, location: str, check_in: str, check_out: str, guests: int = 2
    ) -> str:
        """Query only the hotel agent."""
        return await self._ask(
            "hotel",
            f"请搜索「{location}」的真实酒店，入住 {check_in}，退房 {check_out}，"
            f"入住人数 {guests} 人。",
        )

    async def search_trains_only(
        self, start: str, end: str, date: str = "", is_high_speed: int = 0
    ) -> str:
        """Query only the train agent."""
        return await self._ask(
            "train",
            f"请查询 {date or '近期'} 从「{start}」到「{end}」的真实"
            f"{'高铁' if is_high_speed else '火车'}票。",
        )


travel_workflow = TravelPlanningWorkflow()
