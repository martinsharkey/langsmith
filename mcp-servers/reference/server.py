#!/usr/bin/env python3
"""Example MCP server: read-only lookup in a small reference set, over streamable HTTP.

It stands for a client system exposed to agents as tools. `delete_reference` exists to show the agent's allowlist
working: the server offers it, the agent never receives it.

    python server.py            # serves http://127.0.0.1:9100/mcp
"""
from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

REFERENCE = {
    "AD-57": "Every Agent Server deployment ships custom auth and a per-user store auth handler.",
    "AD-59": "Agents reach models only through the LLM Gateway using model classes.",
}

mcp = FastMCP("reference", host=os.environ.get("MCP_HOST", "127.0.0.1"), port=int(os.environ.get("MCP_PORT", "9100")))


@mcp.tool()
def lookup_reference(key: str) -> str:
    """Return the reference entry for a decision key such as AD-59."""
    entry = REFERENCE.get(key.strip().upper())
    return f"{key}: {entry} (source: reference MCP server)" if entry else f"No entry for {key}."


@mcp.tool()
def delete_reference(key: str) -> str:
    """Delete a reference entry. Not on any agent's allowlist."""
    return f"Deletion of {key} is not available."


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
