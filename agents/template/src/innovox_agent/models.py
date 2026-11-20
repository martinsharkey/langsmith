"""Model access. Agents name a model class; the LangSmith LLM Gateway decides where it runs (AD-31, AD-59).

No provider or model name appears in agent code. Moving a class to another model or provider is a gateway
configuration change, approved through the model intake gate.
"""

from __future__ import annotations

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

from innovox_agent import settings


def model_for(model_class: str | None = None) -> BaseChatModel:
    cfg = settings.load()
    return init_chat_model(
        model=model_class or cfg.model_class,
        model_provider="openai",  # the gateway's OpenAI-compatible endpoint, not OpenAI
        base_url=cfg.gateway_base_url,
        api_key=cfg.gateway_api_key or "unset",
    )
