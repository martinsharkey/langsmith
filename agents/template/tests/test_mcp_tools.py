import asyncio

from innovox_agent import mcp_tools, settings
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


def run_lookup(thread):
    model = scripted(tool_call("lookup_reference", {"key": "AD-59"}), AIMessage(content="Found it."))
    agent = build_agent(model=model, extra_tools=[lookup_reference], checkpointer=InMemorySaver(),
                        store=InMemoryStore())
    return agent.invoke({"messages": [{"role": "user", "content": "Look up AD-59"}]},
                        {"configurable": {"thread_id": thread}})


def test_allowlisted_mcp_tool_pauses_for_approval_by_default(monkeypatch):
    """An MCP tool can write, send or delete; unless the deployment names it read-only, a person approves it."""
    monkeypatch.delenv("MCP_READ_ONLY_TOOLS", raising=False)
    result = run_lookup("t-mcp-default")
    assert result.get("__interrupt__"), "an allowlisted MCP tool must pause for approval by default"
    assert not any(m.type == "tool" and m.name == "lookup_reference" for m in result["messages"])


def test_read_only_mcp_tool_runs_without_pausing(monkeypatch):
    monkeypatch.setenv("MCP_READ_ONLY_TOOLS", " lookup_reference ,")
    assert settings.load().mcp_read_only_tools == frozenset({"lookup_reference"})
    result = run_lookup("t-mcp-read-only")
    assert "__interrupt__" not in result
    assert any(m.type == "tool" and m.content == "AD-59: entry" for m in result["messages"])


class SlowClient:
    """Stands in for the adapter's MultiServerMCPClient; the pause makes a second load wait on the lock."""

    def __init__(self, connections):
        self.connections = connections

    async def get_tools(self):
        await asyncio.sleep(0.01)
        return [lookup_reference, delete_reference]


def test_loader_works_on_more_than_one_event_loop(monkeypatch):
    """Agent Server may build graphs on more than one event loop; the loader's lock must not be tied to one."""
    from langchain_mcp_adapters import client as adapter

    monkeypatch.setattr(adapter, "MultiServerMCPClient", SlowClient)
    monkeypatch.setenv("MCP_SERVERS", '{"reference": {"transport": "http", "url": "http://127.0.0.1:1/mcp"}}')
    monkeypatch.setenv("MCP_ALLOWED_TOOLS", "lookup_reference")
    monkeypatch.setattr(mcp_tools, "_cache", None)

    async def two_loads():
        return await asyncio.gather(mcp_tools.load_mcp_tools(), mcp_tools.load_mcp_tools())

    for _ in range(2):  # two separate event loops
        mcp_tools._cache = None
        loaded = asyncio.run(two_loads())
        assert [[t.name for t in tools] for tools in loaded] == [["lookup_reference"], ["lookup_reference"]]


def test_supervisor_tracks_background_tasks():
    agent = build_agent(model=scripted(AIMessage(content="ok")))
    assert "async_tasks" in agent.channels, "the analyst async subagent must be registered"
