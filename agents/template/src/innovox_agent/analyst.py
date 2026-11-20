"""A second graph in the same deployment, used by the supervisor as an async (background) subagent.

It runs on its own thread through the Agent Protocol, so the user can keep working with the supervisor while it
runs, and it reports back when it finishes. It is a deep agent because only deep agents can notify an idle
supervisor (LangChain: async subagents).
"""

from __future__ import annotations

from typing import Any

from deepagents import create_deep_agent
from langchain_core.language_models import BaseChatModel

from innovox_agent.models import model_for
from innovox_agent.settings import load
from innovox_agent.tools import search_documents

ANALYST_PROMPT = """You carry out one analysis task in the background. Use `search_documents` for facts, cite
the document keys you used, and finish with a short written result. You cannot ask the user questions."""


def build_analyst(model: BaseChatModel | None = None, **kwargs: Any):
    return create_deep_agent(
        model=model or model_for(load().subagent_model_class),
        tools=[search_documents],
        system_prompt=ANALYST_PROMPT,
        name="innovox-analyst",
        **kwargs,
    )


analyst = build_analyst()
