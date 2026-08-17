"""Shared LLM factory for the SmartVoyage system.

集中管理 DeepSeek（OpenAI 兼容）客户端实例，供意图识别、行程规划、闲聊等
模块复用，避免在各处重复配置 API Key / Base URL。
"""

import logging
from typing import Any

from langchain_openai import ChatOpenAI

from configs.settings import settings

logger = logging.getLogger(__name__)


def get_chat_llm(temperature: float = 0.1) -> ChatOpenAI:
    """Return a configured ChatOpenAI (DeepSeek-compatible) instance.

    Args:
        temperature: 采样温度，越低越稳定（意图识别/规划用低值，闲聊用高值）。

    Returns:
        已配置的 ChatOpenAI 客户端。
    """
    return ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        temperature=temperature,
    )
