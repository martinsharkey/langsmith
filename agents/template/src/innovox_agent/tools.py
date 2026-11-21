"""Example tools. Replace with MCP tools from the client's approved servers (langchain MCP adapter).

`publish_document` stands for any action with an effect outside the platform. It is listed in the agent's
`interrupt_on`, so a person must approve, edit or reject every call (CTL-14).
"""

from __future__ import annotations

from langchain_core.tools import tool

_CORPUS = {
    "DP-AI-001": "Sovereign Agentic Platform: self-hosted LangSmith, deep agents, LLM Gateway, vLLM model classes.",
    "AD-59": "Agents reach models only through the LLM Gateway using model classes.",
    "AD-57": "Every Agent Server deployment ships custom auth and a per-user store auth handler.",
}


@tool
def search_documents(query: str) -> str:
    """Search the reference documents and return matching passages."""
    words = [w for w in query.lower().split() if len(w) > 2]
    hits = [f"{key}: {text}" for key, text in _CORPUS.items()
            if any(w in (key + " " + text).lower() for w in words)]
    return "\n".join(hits) if hits else "No matching passages."


@tool
def publish_document(title: str, body: str) -> str:
    """Publish a finished document outside the platform. Requires human approval."""
    return f"Published '{title}' ({len(body)} characters)."


TOOLS = [search_documents, publish_document]
APPROVAL_REQUIRED = {"publish_document": True}
