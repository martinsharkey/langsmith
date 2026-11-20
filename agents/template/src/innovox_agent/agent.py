"""The template deep agent: a supervisor that plans, delegates research to a subagent, keeps per-user memory and
pauses for approval before any external action. Deployed to Agent Server through langgraph.json."""

from __future__ import annotations

from typing import Any

from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend
from langchain_core.language_models import BaseChatModel

from .models import model_for
from .settings import load
from .tools import APPROVAL_REQUIRED, TOOLS, search_documents

SYSTEM_PROMPT = """You are an Innovox task agent. Work methodically:

1. For multi-step work, write a short plan first and keep it up to date.
2. Delegate research to the `researcher` subagent and use its findings; do not invent facts.
3. Write drafts to files, not into the conversation.
4. You have persistent memory at /memories/. Read /memories/preferences.md at the start of a task if it exists,
   and record lasting user preferences there.
5. `publish_document` sends work outside the platform. Call it only when the user has asked for publication;
   a person will be asked to approve it.
"""

RESEARCHER_PROMPT = """You research questions using `search_documents` and reply with a concise summary that
cites the document keys you used. If nothing relevant is found, say so."""


def memory_namespace(runtime: Any) -> tuple[str, ...]:
    """Long-term memory is scoped to the assistant and the signed-in user (LangChain's recommended scoping)."""
    info = getattr(runtime, "server_info", None)
    user = getattr(getattr(info, "user", None), "identity", None)
    assistant = getattr(info, "assistant_id", None)
    return (str(assistant or "local"), str(user or "anonymous"), "memories")


def build_agent(model: BaseChatModel | None = None, subagent_model: BaseChatModel | None = None, **kwargs: Any):
    cfg = load()
    return create_deep_agent(
        model=model or model_for(cfg.model_class),
        tools=TOOLS,
        system_prompt=SYSTEM_PROMPT,
        subagents=[
            {
                "name": "researcher",
                "description": "Finds and summarises passages from the reference documents.",
                "system_prompt": RESEARCHER_PROMPT,
                "tools": [search_documents],
                "model": subagent_model or model or model_for(cfg.subagent_model_class),
            }
        ],
        backend=CompositeBackend(
            default=StateBackend(),
            routes={"/memories/": StoreBackend(namespace=memory_namespace)},
        ),
        interrupt_on=APPROVAL_REQUIRED,
        name="innovox-task-agent",
        **kwargs,
    )


agent = build_agent()
