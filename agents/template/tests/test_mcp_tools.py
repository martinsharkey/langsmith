import asyncio

from innovox_agent import mcp_tools
from innovox_agent.agent import build_agent
from fakes import scripted, tool_call
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore


@tool
def lookup_reference(key: str) -> str:
    """Look up a reference entry."""
    return f"{key}: entry"


@tool
def delete_reference(key: str) -> str:
    """Delete a reference entry."""
    return "deleted"


def test_only_allowlisted_mcp_tools_are_kept():
    kept = mcp_tools.allowed([lookup_reference, delete_reference], {"lookup_reference"})
    assert [t.name for t in kept] == ["lookup_reference"]


def test_no_allowlist_means_no_mcp_tools():
    assert mcp_tools.allowed([lookup_reference, delete_reference], set()) == []


def test_nothing_is_loaded_without_configuration(monkeypatch):
    monkeypatch.delenv("MCP_SERVERS", raising=False)
    monkeypatch.delenv("MCP_ALLOWED_TOOLS", raising=False)
    assert asyncio.run(mcp_tools.load_mcp_tools()) == []


def test_servers_without_an_allowlist_load_nothing(monkeypatch):
    monkeypatch.setenv("MCP_SERVERS", '{"reference": {"transport": "http", "url": "http://127.0.0.1:1/mcp"}}')
    monkeypatch.delenv("MCP_ALLOWED_TOOLS", raising=False)
    assert asyncio.run(mcp_tools.load_mcp_tools()) == []


def test_agent_can_call_an_mcp_tool_passed_as_extra():
    model = scripted(tool_call("lookup_reference", {"key": "AD-59"}), AIMessage(content="Found it."))
    agent = build_agent(model=model, extra_tools=[lookup_reference], checkpointer=InMemorySaver(),
                        store=InMemoryStore())
    result = agent.invoke({"messages": [{"role": "user", "content": "Look up AD-59"}]},
                          {"configurable": {"thread_id": "t-mcp"}})
    assert any(m.type == "tool" and m.content == "AD-59: entry" for m in result["messages"])


def test_supervisor_tracks_background_tasks():
    agent = build_agent(model=scripted(AIMessage(content="ok")))
    assert "async_tasks" in agent.channels, "the analyst async subagent must be registered"
