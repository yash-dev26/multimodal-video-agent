"""
Deterministic, zero-network stand-ins for the ChatGroq instances that
multimodal_agent.agent.llm's factory functions (build_routing_llm,
build_tool_use_llm, build_general_llm, build_finalize_llm) normally return.

None of these subclass LangChain's BaseChatModel -- every agent node only
ever calls `.with_structured_output(...)`, `.bind_tools(...)`, or
`.invoke(...)` on whatever the factory gives it (see router.py,
general_response.py, tool_agent.py, finalize.py), so a plain duck-typed
class is enough and sidesteps LangChain's real structured-output/function-
calling machinery entirely.

Each instance is scripted per-test: you decide up front exactly what it
will return, in order, and it raises loudly if a node calls it more times
than expected -- an assertion failure here almost always means the graph
took an unexpected path, which is itself useful signal.
"""

from __future__ import annotations

from typing import Any


class ScriptExhausted(AssertionError):
    pass


class FakeStructuredLLM:
    """What `fake_llm.with_structured_output(SomeModel)` returns.

    `.invoke(messages)` ignores `messages` entirely and just pops the next
    pre-built Pydantic instance off the queue -- the node under test never
    needs a real LLM to have "reasoned" its way to that instance.
    """

    def __init__(self, schema: type, responses: list[Any]):
        self._schema = schema
        self._responses = list(responses)

    def invoke(self, messages: Any) -> Any:
        if not self._responses:
            raise ScriptExhausted(
                f"FakeStructuredLLM for {self._schema.__name__}: no more "
                f"canned responses queued, but a node called .invoke() again."
            )
        return self._responses.pop(0)


class FakeToolCallingLLM:
    """What `fake_llm.bind_tools(tools)` returns.

    `.invoke(messages)` pops the next canned AIMessage off the queue.
    tool_agent.py is the only caller (`llm_with_tools.invoke(history)`);
    each pass through the ReAct tool-use loop consumes one entry, so the
    queue length should equal the number of tool_agent node visits the
    test expects for the scenario under test.
    """

    def __init__(self, ai_messages: list[Any]):
        self._messages = list(ai_messages)

    def invoke(self, messages: Any) -> Any:
        if not self._messages:
            raise ScriptExhausted(
                "FakeToolCallingLLM: no more canned AIMessages queued, but "
                "tool_agent_node called .invoke() again -- the graph looped "
                "more times than the test scripted for."
            )
        return self._messages.pop(0)


class FakeChatModel:
    """Drop-in replacement for one of build_routing_llm() / build_tool_use_llm()
    / build_general_llm() / build_finalize_llm()'s return values.

    Construct one **per factory you need to patch** in a given test.
    finalize.py calls `.with_structured_output()` twice on the SAME llm
    instance (once for GeneralResponseModel, once for VideoClipResponseModel)
    -- pass both schemas' queues into one FakeChatModel if the test exercises
    both branches, or just the one it needs.
    """

    def __init__(
        self,
        structured: dict[type, list[Any]] | None = None,
        tool_ai_messages: list[Any] | None = None,
    ):
        self._structured = {k: list(v) for k, v in (structured or {}).items()}
        self._tool_ai_messages = list(tool_ai_messages or [])

    def with_structured_output(self, schema: type) -> FakeStructuredLLM:
        if schema not in self._structured:
            raise ScriptExhausted(
                f"FakeChatModel: test didn't configure any canned responses "
                f"for schema {schema.__name__}, but a node requested "
                f"with_structured_output({schema.__name__})."
            )
        return FakeStructuredLLM(schema, self._structured[schema])

    def bind_tools(self, tools: Any) -> FakeToolCallingLLM:
        return FakeToolCallingLLM(self._tool_ai_messages)


def patch_llms(
    monkeypatch: Any,
    *,
    router: FakeChatModel | None = None,
    tool_use: FakeChatModel | None = None,
    general: FakeChatModel | None = None,
    finalize: FakeChatModel | None = None,
) -> None:
    """Patch the LLM factories at the module where the graph uses them."""
    from multimodal_agent.agent.graph import graph as graph_module

    replacements = {
        "build_routing_llm": router,
        "build_tool_use_llm": tool_use,
        "build_general_llm": general,
        "build_finalize_llm": finalize,
    }
    for factory_name, fake_llm in replacements.items():
        if fake_llm is not None:
            monkeypatch.setattr(graph_module, factory_name, lambda fake_llm=fake_llm: fake_llm)


def patch_llms_noop(monkeypatch: Any) -> None:
    """Patch every graph LLM factory with a model that is never invoked."""
    noop = FakeChatModel()
    patch_llms(
        monkeypatch,
        router=noop,
        tool_use=noop,
        general=noop,
        finalize=noop,
    )
