"""
I5, I6: real Postgres-backed chat memory, proven across independent HTTP
requests rather than within a single graph.ainvoke() call.
"""

import uuid

import pytest

from multimodal_agent.models import GeneralResponseModel, RoutingResponseModel
from tests.fakes.fake_llm import FakeChatModel
from tests.helpers import patch_llms


def _recording_general_llm(canned_messages: list[str]) -> tuple[FakeChatModel, list[list]]:
    """A FakeChatModel for build_general_llm() that also records the full
    message history it was invoked with on each call.

    general_response_node is the node to observe memory persistence
    through: it invokes its LLM with the FULL `state["messages"]` history
    (router_node, by contrast, only ever looks at the single latest
    HumanMessage -- see router.py -- so it can't be used to prove this).
    """
    seen_histories: list[list] = []
    llm = FakeChatModel(structured={GeneralResponseModel: [GeneralResponseModel(message=m) for m in canned_messages]})

    real_with_structured_output = llm.with_structured_output

    def _recording_with_structured_output(schema):
        inner = real_with_structured_output(schema)
        real_invoke = inner.invoke

        def _invoke(messages):
            seen_histories.append(list(messages))
            return real_invoke(messages)

        inner.invoke = _invoke
        return inner

    llm.with_structured_output = _recording_with_structured_output
    return llm, seen_histories


@pytest.mark.asyncio
async def test_thread_persists_across_turns(monkeypatch, make_client, mcp_script):
    """I5: the Postgres checkpointer must persist conversation history
    ACROSS independent HTTP requests for the same thread_id, not just
    within a single graph invocation.
    """
    general_llm, seen_histories = _recording_general_llm(["Hi there!", "Yes, I remember — blue!"])

    patch_llms(
        monkeypatch,
        router=FakeChatModel(
            structured={RoutingResponseModel: [RoutingResponseModel(tool_use=False), RoutingResponseModel(tool_use=False)]}
        ),
        general=general_llm,
    )

    thread_id = str(uuid.uuid4())

    async with make_client() as client:
        r1 = await client.post("/chat", json={"message": "my favorite color is blue", "thread_id": thread_id})
        assert r1.status_code == 200
        assert r1.json()["thread_id"] == thread_id

        r2 = await client.post("/chat", json={"message": "what's my favorite color?", "thread_id": thread_id})
        assert r2.status_code == 200
        assert r2.json()["message"] == "Yes, I remember — blue!"

    assert len(seen_histories) == 2
    first_call_humans = [m.content for m in seen_histories[0] if m.type == "human"]
    second_call_humans = [m.content for m in seen_histories[1] if m.type == "human"]

    assert first_call_humans == ["my favorite color is blue"]
    # The second invocation must see BOTH turns' human messages -- proof
    # the Postgres checkpoint round-tripped real history across two
    # independent HTTP requests, not just within one graph.ainvoke() call.
    assert second_call_humans == ["my favorite color is blue", "what's my favorite color?"]


@pytest.mark.asyncio
async def test_reset_memory_clears_checkpoint(monkeypatch, make_client, mcp_script):
    """I6: /reset-memory must actually delete the Postgres checkpoint, not
    just return 200. api.py's endpoint has a silent no-op fallback when
    the checkpointer backend doesn't support deletion (AsyncPostgresSaver
    does, via adelete_thread) -- a 200 response alone can't distinguish
    "deleted" from "silently skipped", so this proves it via a THIRD /chat
    call and checks the history it saw starts over.
    """
    general_llm, seen_histories = _recording_general_llm(["Hi there!", "Hello again, fresh start!"])

    patch_llms(
        monkeypatch,
        router=FakeChatModel(
            structured={RoutingResponseModel: [RoutingResponseModel(tool_use=False), RoutingResponseModel(tool_use=False)]}
        ),
        general=general_llm,
    )

    thread_id = str(uuid.uuid4())

    async with make_client() as client:
        r1 = await client.post("/chat", json={"message": "remember this: pineapple", "thread_id": thread_id})
        assert r1.status_code == 200

        reset_resp = await client.post("/reset-memory", json={"thread_id": thread_id})
        assert reset_resp.status_code == 200

        r2 = await client.post("/chat", json={"message": "hello again", "thread_id": thread_id})
        assert r2.status_code == 200

    assert len(seen_histories) == 2
    second_call_humans = [m.content for m in seen_histories[1] if m.type == "human"]
    # If the reset were a silent no-op, this would include "remember this:
    # pineapple" from the first turn too.
    assert second_call_humans == ["hello again"]
