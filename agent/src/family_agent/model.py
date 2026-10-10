"""Dựng model LLM tương thích OpenAI từ settings (spec §5)."""

from __future__ import annotations

from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings

from family_agent.settings import Settings

MAX_RETRIES = 1


def build_model(settings: Settings) -> OpenAIChatModel:
    model_settings = ModelSettings(timeout=settings.llm_timeout_s)
    if settings.llm_temperature is not None:
        model_settings["temperature"] = settings.llm_temperature
    if settings.llm_max_tokens is not None:
        model_settings["max_tokens"] = settings.llm_max_tokens
    return OpenAIChatModel(
        settings.llm_model,
        provider=OpenAIProvider(
            openai_client=AsyncOpenAI(
                base_url=settings.llm_base_url,
                api_key=settings.llm_api_key.get_secret_value(),
                timeout=settings.llm_timeout_s,
                # Mặc định retry 2 lần × timeout → timeout cứng của lượt luôn cắt trước; giữ 1 lần.
                max_retries=MAX_RETRIES,
            )
        ),
        settings=model_settings,
    )
