#!/usr/bin/env python3
"""A second MCP server for end-to-end tests only: one tool with an outside effect.

`file_reference_note` stands for a client tool that writes. The e2e stack puts it on the agent's allowlist but not
on `MCP_READ_ONLY_TOOLS`, so the agent must pause for a person's approval before it runs (CTL-14).

    python e2e/mcp_notes_server.py      # serves http://127.0.0.1:9101/mcp
"""
from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("notes", host="127.0.0.1", port=int(os.environ.get("MCP_NOTES_PORT", "9101")))
NOTES: dict[str, list[str]] = {}


@mcp.tool()
def file_reference_note(key: str, note: str) -> str:
    """File a review note against a decision key such as AD-59."""
    NOTES.setdefault(key, []).append(note)
    return f"Note filed for {key} (source: notes MCP server)"


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
