"""The template deep agent: a supervisor that plans, delegates research to a subagent, keeps per-user memory and
pauses for approval before any external action. Deployed to Agent Server through langgraph.json."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend
from langchain.agents.middleware import TodoListMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import RunnableConfig

from innovox_agent.mcp_tools import load_mcp_tools
from innovox_agent.models import model_for
from innovox_agent.settings import load
from innovox_agent.tools import APPROVAL_REQUIRED, TOOLS, search_documents

SYSTEM_PROMPT = """You are an Innovox task agent. Work methodically:

1. For multi-step work, write a short plan first and keep it up to date.
2. Delegate research to the `researcher` subagent and use its findings; do not invent facts.
3. Write drafts to files, not into the conversation.
4. You have persistent memory at /memories/. Read /memories/preferences.md at the start of a task if it exists,
   and record lasting user preferences there.
5. For long analysis the user should not wait for, start the `analyst` background task and carry on; you will be
   told when it finishes.
6. `publish_document` sends work outside the platform. Call it only when the user has asked for publication;
   a person will be asked to approve it.
"""

RESEARCHER_PROMPT = """You research questions using `search_documents` and reply with a concise summary that
cites the document keys you used. If nothing relevant is found, say so."""


def memory_namespace(runtime: Any) -> tuple[str, ...]:
    """Long-term memory is scoped to the assistant and the signed-in user (LangChain's recommended scoping).

    A run with no user identity (a cron run, a misconfigured deployment) gets no memory rather than a namespace
    shared with every other such run (T-13, CTL-15). `INNOVOX_ALLOW_ANONYMOUS_MEMORY=1` allows a shared local
    namespace for development without sign-in only. PermissionError, not AttributeError: Deep Agents' StoreBackend
    re-raises an AttributeError from the factory as a different error when there is no runtime.
    """
    info = getattr(runtime, "server_info", None)
    user = getattr(getattr(info, "user", None), "identity", None)
    assistant = getattr(info, "assistant_id", None)
    if not user:
        if not load().allow_anonymous_memory:
            raise PermissionError("Long-term memory needs a signed-in user; this run has no user identity")
        user = "anonymous"
    return (str(assistant or "local"), str(user), "memories")


def approval_required(extra_tools: Sequence[Any], read_only: frozenset[str]) -> dict[str, bool]:
    """The built-in tools that need approval, plus every MCP tool the deployment has not named read-only.

    MCP tools fail closed: a newly allowlisted tool pauses for a person until someone declares it read-only."""
    return {**APPROVAL_REQUIRED, **{tool.name: True for tool in extra_tools if tool.name not in read_only}}


def build_agent(
    model: BaseChatModel | None = None,
    subagent_model: BaseChatModel | None = None,
    extra_tools: Sequence[Any] = (),
    **kwargs: Any,
):
    """`extra_tools` are the allowlisted MCP tools, loaded by `make_agent` when the server builds the graph."""
    cfg = load()
    return create_deep_agent(
        model=model or model_for(cfg.model_class),
        tools=[*TOOLS, *extra_tools],
        system_prompt=SYSTEM_PROMPT,
        subagents=[
            {
                "name": "researcher",
                "description": "Finds and summarises passages from the reference documents.",
                "system_prompt": RESEARCHER_PROMPT,
                "tools": [search_documents],
                "model": subagent_model or model or model_for(cfg.subagent_model_class),
            },
            # An async subagent: the `analyst` graph in this deployment (langgraph.json), reached in-process.
            {
                "name": "analyst",
                "description": "Runs a longer analysis in the background and reports back when it is finished.",
                "graph_id": "analyst",
            },
        ],
        backend=CompositeBackend(
            default=StateBackend(),
            routes={"/memories/": StoreBackend(namespace=memory_namespace)},
        ),
        # Planning is opt-in since Deep Agents 0.7; the workbench renders the plan from the `todos` state.
        middleware=[TodoListMiddleware()],
        interrupt_on=approval_required(extra_tools, cfg.mcp_read_only_tools),
        name="innovox-task-agent",
        **kwargs,
    )


async def make_agent(config: RunnableConfig):
    """Graph factory named in langgraph.json. Agent Server calls it when it needs the graph, which lets the agent
    pick up its MCP tools (an async call) before it is built."""
    return build_agent(extra_tools=await load_mcp_tools())
