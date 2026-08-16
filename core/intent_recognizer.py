"""Intent recognition using LLM."""

import json
import logging
from typing import Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from configs.settings import settings
from models.schemas import IntentType, IntentResult

logger = logging.getLogger(__name__)


class IntentRecognizer:
    """Recognizes user intent from natural language input."""

    def __init__(self):
        """Initialize intent recognizer with LLM."""
        self.llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            temperature=0.1,
        )

        # Intent recognition prompt
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """你是一个智能旅行助手的意图识别模块。你的任务是分析用户的输入，识别用户的意图类型，并提取关键信息（槽位）。

可用的意图类型：
1. weather_query - 天气查询（用户询问某个城市的天气）
2. flight_booking - 机票预订（用户想查询或预订机票）
3. train_booking - 高铁/火车票查询（用户想查询或预订高铁票、火车票）
4. hotel_booking - 酒店预订（用户想查询或预订酒店）
5. itinerary_planning - 行程规划（用户想规划一个完整的旅行行程）
6. general_qa - 通用问答（其他问题）

请分析用户输入，返回JSON格式的结果，包含：
- intent: 意图类型（从上述6种中选择）
- confidence: 置信度（0-1之间的浮点数）
- slots: 提取的槽位信息，可能包含：
  - destination: 目的地城市
  - departure: 出发城市
  - date: 日期
  - duration: 天数
  - budget: 预算
  - guests: 人数
  - check_in: 入住日期
  - check_out: 退房日期

只返回JSON，不要其他内容。"""),
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

            # Call LLM
            response = await self.llm.ainvoke(messages)
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

            return IntentResult(
                intent=intent,
                confidence=confidence,
                slots=slots,
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            return IntentResult(
                intent=IntentType.GENERAL_QA,
                confidence=0.5,
                slots={},
            )
        except Exception as e:
            logger.exception(f"Error recognizing intent: {e}")
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
