"""Intent recognition using LLM."""

import json
import logging
from typing import Dict, Any, Optional
from langchain_core.prompts import ChatPromptTemplate
from core.llm import get_chat_llm
from core.slot_filler import (
    INTENT_CANDIDATE_SKILLS,
    SKILL_DESCRIPTIONS,
    SKILL_PARAMETERS,
)
from models.schemas import IntentType, IntentResult

logger = logging.getLogger(__name__)


class IntentRecognizer:
    """Recognizes user intent from natural language input."""

    def __init__(self):
        """Initialize intent recognizer."""
        skill_lines = [
            f"- {name}（{SKILL_DESCRIPTIONS.get(name, '')}）：参数 {', '.join(params)}"
            for name, params in SKILL_PARAMETERS.items()
        ]
        intent_skill_lines = [
            f"- {intent}: {', '.join(skills)}"
            for intent, skills in INTENT_CANDIDATE_SKILLS.items()
        ]
        skills_text = "\n".join(skill_lines)
        intent_skill_text = "\n".join(intent_skill_lines)

        system_prompt = """你是一个智能旅行助手的意图识别、技能选择与槽位提取模块。

可用的意图类型：
1. weather_query - 天气查询
2. flight_booking - 机票/航班查询
3. train_booking - 高铁/火车票查询
4. hotel_booking - 酒店或景点查询
5. itinerary_planning - 完整行程规划
6. general_qa - 其他通用问答

【意图与候选技能】
__INTENT_SKILLS__

【可选择的 skill（必须从以下完整列表中选择）】
__SKILLS__

【槽位提取规则】
1. 只提取用户明确说出、或能从原话直接确定的信息。
2. 没有提到的字段不要输出、不要猜测、不要编造，也不要用示例值填充。
3. 日期统一输出 YYYY-MM-DD；今天/明天/后天等按当前日期换算。
4. 城市只输出中文城市名，去掉“市/省”等后缀；人数、天数、预算输出数字。
5. 同一句话里同时出现出发地和目的地时，分别填 departure 和 destination。
6. 无法确定的字段直接省略或填 null。

【可提取的 slots（按需提取，不要全部返回）】
城市/地点：
- destination: 目的地城市
- departure: 出发城市
- location: 查询城市（天气/酒店/景点，通常等于 destination）
- start: 火车出发城市或车站（通常等于 departure）
- end: 火车到达城市或车站（通常等于 destination）
- arrival: 航班到达城市（通常等于 destination）

日期/时长：
- date: 出行日期
- start_date: 行程开始日期
- check_in: 酒店入住日期
- check_out: 酒店退房日期
- duration: 行程天数（整数）
- days: 天气预报天数（整数）

人数/预算：
- guests: 出行或入住人数（整数）
- passengers: 航班乘客人数（整数，通常等于 guests）
- budget: 预算金额（数字，人民币）

交通/酒店：
- flight_no: 航班号（如 MU5100）
- hotel_name: 酒店名称
- is_high_speed: 是否只查高铁（1 或 0）
- max_segments: 航班最大航段数（整数）

其他：
- limit: 返回数量上限（整数）
- user_id: 用户 ID（只有用户明确写出时才提取）

【skill 选择规则】
1. skill 必须从上面完整技能列表中选择，并且必须属于该 intent 的候选技能。
2. 航班号 → get_flight_detail；按城市/日期查航班 → search_flights。
3. 未来/预报/几天 → get_forecast；当前天气 → get_current_weather。
4. 景点/好玩/攻略 → search_attractions；酒店名称 + 详情 → get_hotel_detail；否则 hotel_booking 默认 search_hotels。
5. 无法确定时选择该 intent 默认的第一个候选技能。

只返回 JSON，例如：
{{"intent": "weather_query", "skill": "get_current_weather", "confidence": 0.9, "slots": {{"destination": "北京", "days": 3}}}}
不要输出 Markdown 代码块或任何额外解释。"""

        system_prompt = system_prompt.replace("__INTENT_SKILLS__", intent_skill_text)
        system_prompt = system_prompt.replace("__SKILLS__", skills_text)
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{input}"),
        ])

    async def recognize(self, user_input: str) -> IntentResult:
        """
        Recognize intent from user input.

        Args:
            user_input: User's natural language input

        Returns:
            IntentResult with intent type, confidence, and slots
        """
        try:
            # Format prompt
            messages = self.prompt.format_messages(input=user_input)

            # Call LLM（缺少 Key 时会抛出明确错误，随后降级为规则识别）
            llm = get_chat_llm(temperature=0.1)
            response = await llm.ainvoke(messages)
            content = response.content.strip()

            # Parse JSON response
            # Handle case where LLM wraps JSON in markdown code block
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            result = json.loads(content)

            # Map to IntentResult
            intent_str = result.get("intent", "general_qa")
            try:
                intent = IntentType(intent_str)
            except ValueError:
                intent = IntentType.GENERAL_QA

            confidence = float(result.get("confidence", 0.8))
            slots = result.get("slots", {})

            skill = result.get("skill")
            if skill not in SKILL_PARAMETERS:
                skill = None
            candidates = INTENT_CANDIDATE_SKILLS.get(intent.value, [])
            if skill and candidates and skill not in candidates:
                skill = None

            return IntentResult(
                intent=intent,
                confidence=confidence,
                slots=slots,
                skill=skill,
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            return IntentResult(
                intent=IntentType.GENERAL_QA,
                confidence=0.5,
                slots={},
            )
        except Exception as e:
            # LLM 不可用（如余额不足/网络故障）时，降级为规则识别，只记一条简洁告警
            logger.warning(f"LLM 意图识别不可用，将降级为规则识别: {e}")
            return IntentResult(
                intent=IntentType.GENERAL_QA,
                confidence=0.0,
                slots={},
            )

    async def recognize_with_fallback(self, user_input: str) -> IntentResult:
        """
        Recognize intent with fallback to rule-based detection.

        Args:
            user_input: User's natural language input

        Returns:
            IntentResult
        """
        # First try LLM recognition
        result = await self.recognize(user_input)

        # If confidence is too low, try rule-based fallback
        if result.confidence < 0.6:
            rule_result = self._rule_based_recognize(user_input)
            if rule_result.confidence > result.confidence:
                return rule_result

        return result

    def _rule_based_recognize(self, user_input: str) -> IntentResult:
        """
        Rule-based intent recognition as fallback.

        Args:
            user_input: User input

        Returns:
            IntentResult
        """
        input_lower = user_input.lower()

        # Weather keywords
        weather_keywords = ["天气", "气温", "下雨", "晴天", "天气预报", "weather"]
        if any(kw in input_lower for kw in weather_keywords):
            return IntentResult(
                intent=IntentType.WEATHER_QUERY,
                confidence=0.7,
                slots={},
            )

        # Flight keywords
        flight_keywords = ["机票", "航班", "飞机", "订票", "flight"]
        if any(kw in input_lower for kw in flight_keywords):
            return IntentResult(
                intent=IntentType.FLIGHT_BOOKING,
                confidence=0.7,
                slots={},
            )

        # Train keywords
        train_keywords = ["高铁", "火车", "动车", "车票", "列车", "train"]
        if any(kw in input_lower for kw in train_keywords):
            return IntentResult(
                intent=IntentType.TRAIN_BOOKING,
                confidence=0.7,
                slots={},
            )

        # Hotel keywords
        hotel_keywords = ["酒店", "住宿", "宾馆", "hotel", "住哪里"]
        if any(kw in input_lower for kw in hotel_keywords):
            return IntentResult(
                intent=IntentType.HOTEL_BOOKING,
                confidence=0.7,
                slots={},
            )

        # Itinerary keywords
        itinerary_keywords = ["行程", "旅行", "旅游", "玩", "规划", "itinerary"]
        if any(kw in input_lower for kw in itinerary_keywords):
            return IntentResult(
                intent=IntentType.ITINERARY_PLANNING,
                confidence=0.7,
                slots={},
            )

        # Default to general QA
        return IntentResult(
            intent=IntentType.GENERAL_QA,
            confidence=0.5,
            slots={},
        )


# Global instance
intent_recognizer = IntentRecognizer()
