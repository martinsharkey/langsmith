import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
from langgraph.types import Command

from fakes import scripted, tool_call
from innovox_agent import models
from innovox_agent.agent import build_agent, memory_namespace
from innovox_agent.tools import search_documents


def run_config(thread="t1"):
    return {"configurable": {"thread_id": thread}}


def test_models_are_gateway_classes_not_providers():
    model = models.model_for()
    assert model.model_name == "custom/class-m"
    assert "gateway" in str(model.openai_api_base)


def test_search_tool_finds_reference_passages():
    assert "AD-59" in search_documents.invoke({"query": "gateway model classes"})
    assert search_documents.invoke({"query": "zzzz"}) == "No matching passages."


def test_memory_namespace_is_per_assistant_and_user():
    class Info:
        assistant_id = "a1"
        user = type("U", (), {"identity": "user-1"})()
    assert memory_namespace(type("R", (), {"server_info": Info()})()) == ("a1", "user-1", "memories")


@pytest.mark.parametrize("runtime", [
    None,  # outside a graph run
    object(),  # no server information, as in a run without a user
    type("R", (), {"server_info": type("I", (), {"assistant_id": "a1", "user": None})()})(),
])
def test_memory_without_a_user_fails_closed(monkeypatch, runtime):
    monkeypatch.delenv("INNOVOX_ALLOW_ANONYMOUS_MEMORY", raising=False)
    with pytest.raises(PermissionError):
        memory_namespace(runtime)


def test_anonymous_memory_only_with_the_development_flag(monkeypatch):
    monkeypatch.setenv("INNOVOX_ALLOW_ANONYMOUS_MEMORY", "1")
    assert memory_namespace(object()) == ("local", "anonymous", "memories")


def test_plain_answer_completes_without_interrupt():
    agent = build_agent(model=scripted(AIMessage(content="Done.")), checkpointer=InMemorySaver(),
                        store=InMemoryStore())
    result = agent.invoke({"messages": [{"role": "user", "content": "Say done."}]}, run_config())
    assert result["messages"][-1].content == "Done."
    assert "__interrupt__" not in result


def test_publication_pauses_for_approval_and_resumes():
    model = scripted(
        tool_call("publish_document", {"title": "Design", "body": "Text"}),
        AIMessage(content="Published as requested."),
    )
    agent = build_agent(model=model, checkpointer=InMemorySaver(), store=InMemoryStore())
    config = run_config("t-approve")
    paused = agent.invoke({"messages": [{"role": "user", "content": "Publish the design."}]}, config)
    assert paused.get("__interrupt__"), "publish_document must pause for a human decision"
    assert not any(getattr(m, "name", None) == "publish_document" and m.type == "tool" for m in paused["messages"])

    resumed = agent.invoke(Command(resume={"decisions": [{"type": "approve"}]}), config)
    tool_results = [m for m in resumed["messages"] if m.type == "tool" and m.name == "publish_document"]
    assert tool_results and "Published 'Design'" in tool_results[-1].content
    assert resumed["messages"][-1].content == "Published as requested."


def test_rejected_publication_never_runs_the_tool():
    model = scripted(
        tool_call("publish_document", {"title": "Design", "body": "Text"}),
        AIMessage(content="Understood, not published."),
    )
    agent = build_agent(model=model, checkpointer=InMemorySaver(), store=InMemoryStore())
    config = run_config("t-reject")
    agent.invoke({"messages": [{"role": "user", "content": "Publish the design."}]}, config)
    resumed = agent.invoke(Command(resume={"decisions": [{"type": "reject", "message": "Not approved"}]}), config)
    assert not any(m.type == "tool" and "Published 'Design'" in str(m.content) for m in resumed["messages"])
