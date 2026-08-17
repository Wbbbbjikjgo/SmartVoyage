"""LLM-powered itinerary planner.

把已收集到的真实数据（天气、景点、酒店、航班/车次）交给大模型，生成一份
真正「可执行」的逐日行程计划：什么时间去哪个景点、怎么去、当天天气如何、
穿什么/带伞等温馨提示，并给出酒店与交通建议。

当 LLM 不可用、返回非法 JSON 或结果为空时，降级为规则化的逐日均分兜底方案，
确保接口始终能返回可用的行程结构。
"""

import json
import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from langchain_core.prompts import ChatPromptTemplate

from core.llm import get_chat_llm

logger = logging.getLogger(__name__)


def format_day_weather(forecast: Optional[Dict[str, Any]]) -> str:
    """将单日预报数据格式化为可读字符串。"""
    if not forecast:
        return ""
    day = forecast.get("day_weather", "")
    day_temp = forecast.get("day_temp", "")
    night_temp = forecast.get("night_temp", "")
    if day_temp or night_temp:
        return f"{day} {night_temp}~{day_temp}°C".strip()
    return day


def build_day_plan(
    start_date: str,
    duration: int,
    weather: Optional[Dict[str, Any]],
    attractions: Optional[List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """规则兜底：按天均分景点，附上当天天气（不含时间安排）。

    Args:
        start_date: 开始日期（YYYY-MM-DD）。
        duration: 行程天数。
        weather: 天气预报结果（含 ``forecast`` 列表）。
        attractions: 景点列表（每项含 ``name``）。

    Returns:
        逐日安排列表。
    """
    try:
        start = date.fromisoformat(start_date)
    except (ValueError, TypeError):
        start = date.today()

    forecasts = (weather or {}).get("forecast", [])
    names = [
        a.get("name")
        for a in (attractions or [])
        if isinstance(a, dict) and a.get("name")
    ]

    days = []
    per_day = max(1, len(names) // max(duration, 1))
    idx = 0
    for d in range(duration):
        day_forecast = forecasts[d] if d < len(forecasts) else None
        day_attractions = names[idx: idx + per_day]
        idx += per_day
        days.append({
            "day": d + 1,
            "date": (start + timedelta(days=d)).isoformat(),
            "weather": format_day_weather(day_forecast),
            "attractions": day_attractions,
            "plan": "",
        })

    # 剩余未分配的景点并入最后一天
    if idx < len(names) and days:
        days[-1]["attractions"].extend(names[idx:])

    return days


class ItineraryPlanner:
    """Generate a day-by-day itinerary from gathered travel data using LLM."""

    _SYSTEM_PROMPT = """你是一名资深的旅行规划师。请根据提供的真实数据（天气、景点、酒店、航班/车次）为用户生成一份专业、可执行的逐日旅行计划。

要求：
1. 严格参考提供的真实数据，不得编造不存在的景点、酒店、航班或车次。
2. 把景点合理分配到每天（每天 2~4 个），并结合当天天气预报安排（如雨天优先安排室内景点，晴天安排户外；高温时段避开正午）。
3. 每天给出具体时间安排（如 09:00）、每个景点的建议游玩时长、景点之间的交通方式建议（地铁/打车/步行等）。
4. 结合天气给出穿衣、防晒、带伞等温馨提示。
5. 推荐最合适的酒店（说明理由），并根据提供的航班/车次给出到达和离开的交通建议。
6. 若提供了预算，请在预算范围内统筹安排。

请严格只返回 JSON，不要包含任何其他文字，格式如下：
{
  "summary": "整体行程概览与建议（2-3句话）",
  "days": [
    {
      "day": 1,
      "date": "2026-08-20",
      "weather": "晴 21~31°C",
      "attractions": ["景点名1", "景点名2"],
      "plan": "08:30 前往景点名1（地铁1号线，约3小时）；13:30 午餐后前往景点名2（打车约20分钟，约2小时）。天气晴好，注意防晒。"
    }
  ],
  "hotel_recommendation": "推荐的酒店及理由",
  "transport_recommendation": "到达/离开的交通建议"
}"""

    def _build_context(
        self,
        meta: Dict[str, Any],
        weather: Optional[Dict[str, Any]],
        attractions: Optional[List[Dict[str, Any]]],
        hotels: Optional[List[Dict[str, Any]]],
        flights: Optional[List[Dict[str, Any]]],
        trains: Optional[List[Dict[str, Any]]],
    ) -> str:
        """把行程元信息与真实数据组装成给 LLM 的上下文。"""
        context = {
            "行程信息": meta,
            "天气预报": (weather or {}).get("forecast", []),
            "景点": attractions or [],
            "酒店": hotels or [],
            "航班": flights or [],
            "车次": trains or [],
        }
        return json.dumps(context, ensure_ascii=False, indent=2)

    async def plan(
        self,
        meta: Dict[str, Any],
        weather: Optional[Dict[str, Any]] = None,
        attractions: Optional[List[Dict[str, Any]]] = None,
        hotels: Optional[List[Dict[str, Any]]] = None,
        flights: Optional[List[Dict[str, Any]]] = None,
        trains: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """生成完整行程计划（LLM，失败时降级为规则规划）。

        Args:
            meta: 行程元信息（destination/start_date/duration/budget/guests/departure）。
            weather: 天气预报结果（含 ``forecast`` 列表）。
            attractions: 景点列表。
            hotels: 酒店列表。
            flights: 航班列表。
            trains: 车次列表。

        Returns:
            含 ``summary``、``days``、``hotel_recommendation``、
            ``transport_recommendation`` 的计划字典。
        """
        try:
            llm = get_chat_llm(temperature=0.4)
            prompt = ChatPromptTemplate.from_messages([
                ("system", self._SYSTEM_PROMPT),
                ("human", "以下是旅行所需的真实数据：\n{context}"),
            ])
            context = self._build_context(
                meta, weather, attractions, hotels, flights, trains
            )
            response = await llm.ainvoke(prompt.format_messages(context=context))
            content = response.content.strip()

            # 兼容 LLM 可能用 markdown 代码块包裹 JSON 的情况
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            plan = json.loads(content)
            days = plan.get("days") or []
            if not days:
                raise ValueError("LLM 未返回 days")

            return {
                "summary": plan.get("summary", ""),
                "hotel_recommendation": plan.get("hotel_recommendation", ""),
                "transport_recommendation": plan.get("transport_recommendation", ""),
                "days": days,
                "source": "llm",
            }
        except Exception as e:
            logger.warning("LLM 行程规划失败，降级为规则规划: %s", e)
            return self._rule_based_plan(meta, weather, attractions)

    def _rule_based_plan(
        self,
        meta: Dict[str, Any],
        weather: Optional[Dict[str, Any]],
        attractions: Optional[List[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        """规则兜底：按天均分景点，无时间安排。"""
        days = build_day_plan(
            meta.get("start_date", ""),
            int(meta.get("duration", 1) or 1),
            weather,
            attractions,
        )
        return {
            "summary": "",
            "hotel_recommendation": "",
            "transport_recommendation": "",
            "days": days,
            "source": "rule",
        }


# Global instance
itinerary_planner = ItineraryPlanner()
