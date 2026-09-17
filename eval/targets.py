"""
Target functions for `langsmith.evaluate()`.

Each target takes a dataset example's `inputs` dict and returns an
`outputs` dict that the matching evaluator (see evaluators.py) knows how
to score. Every target below calls the REAL project component directly
-- no re-implementation -- so the eval exercises the same code path that
runs in production.

Import paths match the repo layout:
  multimodal_agent/src/multimodal_agent/agent/graph/nodes/router.py
  multimodal_agent/src/multimodal_agent/agent/graph/nodes/tool_agent.py
  video_mcp_server/src/video_mcp_server/video/video_search_service.py
  video_mcp_server/src/video_mcp_server/tools.py

Adjust `sys.path` / installs so these import cleanly in whatever process
runs run_evals.py -- e.g. `pip install -e ./multimodal_agent -e
./video_mcp_server` in the eval environment.
"""
from __future__ import annotations

from langchain_core.messages import HumanMessage


# ---------------------------------------------------------------------------
# 1. Router target
# ---------------------------------------------------------------------------

_router_node = None


def _get_router_node():
    global _router_node
    if _router_node is None:
        from multimodal_agent.agent.graph.nodes.router import make_router_node
        from multimodal_agent.agent.llm import build_routing_llm
        from video_mcp_server.prompts import routing_system_prompt

        _router_node = make_router_node(build_routing_llm(), routing_system_prompt())
    return _router_node


def router_target(inputs: dict) -> dict:
    node = _get_router_node()
    state = {"messages": [HumanMessage(content=inputs["message"])]}
    result = node(state)
    return {"needs_tool": result["needs_tool"]}


# ---------------------------------------------------------------------------
# 2. Tool selection target
#
# We only want the tool CHOICE, not a full tool execution -- so this binds
# the tools without running ToolNode, same LLM call `tool_agent_node` makes
# before dispatch.
# ---------------------------------------------------------------------------

_tool_llm = None


def _get_tool_llm():
    """Build the tool-calling LLM without a live MCP server.

    Instead of connecting over HTTP to the MCP server we build
    ``StructuredTool`` objects directly from the real tool functions in
    ``video_mcp_server.tools``.  The LLM therefore receives the exact same
    tool names, descriptions, and JSON schemas that it would see at runtime
    -- only the HTTP transport layer is skipped.
    """
    global _tool_llm
    if _tool_llm is None:
        from langchain_core.tools import StructuredTool
        from multimodal_agent.agent.llm import build_tool_use_llm
        from video_mcp_server.tools import (
            ask_question_about_video,
            get_video_clip_from_image,
            get_video_clip_from_user_query,
        )

        # Mirror the subset of tools the production agent exposes
        # (process_video and remove_video are disabled in targets.py).
        mcp_tools = [
            StructuredTool.from_function(get_video_clip_from_user_query),
            StructuredTool.from_function(get_video_clip_from_image),
            StructuredTool.from_function(ask_question_about_video),
        ]
        _tool_llm = build_tool_use_llm().bind_tools(mcp_tools)
    return _tool_llm


def tool_selection_target(inputs: dict) -> dict:
    from langchain_core.messages import SystemMessage
    from video_mcp_server.prompts import tool_use_system_prompt

    llm = _get_tool_llm()
    system_prompt = tool_use_system_prompt().format(is_image_provided=inputs.get("image_provided", False))
    response = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=inputs["message"])])

    if not response.tool_calls:
        return {"tool": None}
    # tool_agent.py only acts on the first call in practice (video_path/image
    # injection assumes one primary tool per turn) -- score the same way.
    return {"tool": response.tool_calls[0]["name"]}


# ---------------------------------------------------------------------------
# 3. Retrieval target -- calls VideoSearchEngine directly, one modality at a
#    time, so retrieval quality is measured independent of tool selection or
#    the fusion heuristic in get_video_clip_from_user_query.
# ---------------------------------------------------------------------------


def retrieval_target(inputs: dict) -> dict:
    from video_mcp_server.video.video_search_service import VideoSearchEngine

    engine = VideoSearchEngine(inputs["video_path"])
    modality = inputs["modality"]
    top_k = inputs.get("top_k", 5)

    if modality == "speech":
        results = engine.search_by_speech(inputs["query"], top_k)
    elif modality == "caption":
        results = engine.search_by_caption(inputs["query"], top_k)
    elif modality == "image":
        # inputs["query"] holds base64 image data for this modality
        results = engine.search_by_image(inputs["query"], top_k)
    else:
        raise ValueError(f"Unknown modality: {modality}")

    return {
        "windows": [(r["start_time"], r["end_time"]) for r in results],
        "similarities": [r["similarity"] for r in results],
    }


# ---------------------------------------------------------------------------
# 4. QA target -- runs ask_question_about_video AND records the retrieved
#    captions it was built from, so the groundedness evaluator can check the
#    answer against its own supporting context rather than against nothing.
# ---------------------------------------------------------------------------


def qa_target(inputs: dict) -> dict:
    from video_mcp_server.video.video_search_service import VideoSearchEngine
    from video_mcp_server.config import get_settings

    settings = get_settings()
    engine = VideoSearchEngine(inputs["video_path"])
    caption_info = engine.get_caption_info(inputs["question"], settings.QUESTION_ANSWER_TOP_K)
    retrieved_context = [c["caption"] for c in caption_info]
    answer = "\n".join(retrieved_context)

    return {"answer": answer, "retrieved_context": retrieved_context}


# ---------------------------------------------------------------------------
# 5. End-to-end target -- invokes the compiled graph exactly as api.py does.
#    Requires a live checkpointer + MCP server, so this suite is heavier and
#    slower than 1-4; run it less frequently (e.g. pre-release, not per-PR).
# ---------------------------------------------------------------------------


async def _build_graph_once():
    from multimodal_agent.agent.checkpointer import checkpointer_context
    from multimodal_agent.agent.graph.graph import build_graph

    async with checkpointer_context() as checkpointer:
        graph, _ = await build_graph(checkpointer)
        return graph


_graph = None


def e2e_target(inputs: dict) -> dict:
    import asyncio
    from langchain_core.messages import AIMessage

    global _graph
    if _graph is None:
        _graph = asyncio.get_event_loop().run_until_complete(_build_graph_once())

    state = {
        "messages": [HumanMessage(content=inputs["message"])],
        "video_path": inputs.get("video_path"),
        "image_base64": inputs.get("image_base64"),
    }
    config = {"configurable": {"thread_id": f"eval-{hash(inputs['message'])}"}}
    result = _graph.invoke(state, config=config)

    ai_messages = [
        m for m in result.get("messages", [])
        if isinstance(m, AIMessage) and m.content
    ]
    answer = ai_messages[-1].content if ai_messages else ""
    raw_answer = ai_messages[-2].content if len(ai_messages) >= 2 else answer

    return {
        "response_kind": result.get("response_kind"),
        "raw_answer": raw_answer,
        "answer": answer,
        "clip_path": result.get("clip_path"),
    }

