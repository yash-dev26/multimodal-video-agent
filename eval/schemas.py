"""
Dataset shapes for each eval suite, as plain dicts (LangSmith examples are
just {"inputs": {...}, "outputs": {...}} -- no schema enforcement needed,
but keeping these as typed builders stops the datasets from drifting as
more people add examples).

Five suites, matching the five failure surfaces in the pipeline:
  1. router        -- needs_tool binary gate            (router.py)
  2. tool_selection -- which of the 3 MCP tools fires    (tool_agent.py)
  3. retrieval      -- per-modality moment retrieval     (video_search_service.py)
  4. qa             -- ask_question_about_video answers  (tools.py)
  5. e2e            -- full graph, judged end-to-end     (graph.py)
"""
from __future__ import annotations

from typing import Literal, TypedDict


class RouterExample(TypedDict):
    inputs: dict  # {"message": str}
    outputs: dict  # {"needs_tool": bool}


def router_example(message: str, needs_tool: bool) -> RouterExample:
    return {"inputs": {"message": message}, "outputs": {"needs_tool": needs_tool}}


class ToolSelectionExample(TypedDict):
    inputs: dict  # {"message": str, "image_provided": bool, "video_active": bool}
    outputs: dict  # {"tool": str | None}  -- None means "should answer without a tool call"


def tool_selection_example(
    message: str,
    tool: Literal[
        "get_video_clip_from_user_query",
        "get_video_clip_from_image",
        "ask_question_about_video",
        None,
    ],
    image_provided: bool = False,
    video_active: bool = True,
) -> ToolSelectionExample:
    return {
        "inputs": {"message": message, "image_provided": image_provided, "video_active": video_active},
        "outputs": {"tool": tool},
    }


class RetrievalExample(TypedDict):
    inputs: dict  # {"video_path": str, "query": str, "modality": "speech"|"caption"|"image", "top_k": int}
    outputs: dict  # {"gt_windows": [[start, end], ...]}  -- multiple accepted moments allowed


def retrieval_example(
    video_path: str,
    query: str,
    modality: Literal["speech", "caption", "image"],
    gt_windows: list[tuple[float, float]],
    top_k: int = 5,
) -> RetrievalExample:
    return {
        "inputs": {"video_path": video_path, "query": query, "modality": modality, "top_k": top_k},
        "outputs": {"gt_windows": [list(w) for w in gt_windows]},
    }


class QAExample(TypedDict):
    inputs: dict  # {"video_path": str, "question": str}
    outputs: dict  # {"reference_answer": str, "supporting_snippets": [str, ...]}


def qa_example(video_path: str, question: str, reference_answer: str, supporting_snippets: list[str]) -> QAExample:
    return {
        "inputs": {"video_path": video_path, "question": question},
        "outputs": {"reference_answer": reference_answer, "supporting_snippets": supporting_snippets},
    }


class E2EExample(TypedDict):
    inputs: dict  # {"thread_id": str, "message": str, "video_path": str | None, "image_base64": str | None}
    outputs: dict  # {"expected_kind": "general"|"video_clip"|"qa", "reference_answer": str | None, "gt_windows": list | None}


def e2e_example(
    message: str,
    expected_kind: Literal["general", "video_clip", "qa"],
    video_path: str | None = None,
    image_base64: str | None = None,
    reference_answer: str | None = None,
    gt_windows: list[tuple[float, float]] | None = None,
) -> E2EExample:
    return {
        "inputs": {"message": message, "video_path": video_path, "image_base64": image_base64},
        "outputs": {
            "expected_kind": expected_kind,
            "reference_answer": reference_answer,
            "gt_windows": [list(w) for w in gt_windows] if gt_windows else None,
        },
    }
