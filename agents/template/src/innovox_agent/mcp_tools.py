"""Tools from MCP servers, through LangChain's MCP adapter.

Two rules (CTL-14, OWASP Agentic: tool misuse and supply chain):

- servers come only from deployment configuration (`MCP_SERVERS`), never from a prompt or a user;
- a tool is offered to the model only if its name is in `MCP_ALLOWED_TOOLS`. With no allowlist, no MCP tool is
  offered, so a server that later adds a tool cannot widen what the agent can do;
- an offered tool pauses for a person's approval unless its name is also in `MCP_READ_ONLY_TOOLS` (`agent.py`).

`MCP_SERVERS` is the adapter's own connection format, for example
`{"reference": {"transport": "http", "url": "https://mcp.site.example/mcp"}}`.
"""

from __future__ import annotations

import asyncio
import logging
import weakref
from collections.abc import Iterable
from typing import Any

from innovox_agent import settings

log = logging.getLogger(__name__)

# One lock per event loop: an asyncio.Lock is bound to the loop it first waits on, and Agent Server may build
# graphs on more than one loop.
_locks: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Lock] = weakref.WeakKeyDictionary()
_cache: list[Any] | None = None


def allowed(tools: Iterable[Any], allowlist: Iterable[str]) -> list[Any]:
    """Keep only allowlisted tools; log every tool that is withheld."""
    names = set(allowlist)
    kept = []
    for tool in tools:
        if tool.name in names:
            kept.append(tool)
        else:
            log.warning("MCP tool %r is not in MCP_ALLOWED_TOOLS and is withheld from the agent", tool.name)
    return kept


async def load_mcp_tools() -> list[Any]:
    """Load allowlisted MCP tools once per process. An unreachable server is logged and retried on the next run;
    the agent then runs without those tools instead of failing every task."""
    global _cache
    cfg = settings.load()
    if not cfg.mcp_servers or not cfg.mcp_allowed_tools:
        return []
    loop = asyncio.get_running_loop()
    lock = _locks.get(loop)
    if lock is None:
        lock = _locks[loop] = asyncio.Lock()
    async with lock:
        if _cache is None:
            from langchain_mcp_adapters.client import MultiServerMCPClient

            try:
                tools = await MultiServerMCPClient(cfg.mcp_servers).get_tools()
            except Exception:  # noqa: BLE001 - the adapter raises transport-specific errors
                log.exception("Could not load tools from the configured MCP servers")
                return []
            _cache = allowed(tools, cfg.mcp_allowed_tools)
        return list(_cache)
