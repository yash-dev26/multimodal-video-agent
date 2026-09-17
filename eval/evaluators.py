"""
LangSmith evaluator functions: each takes a `Run` (what the target
produced) and an `Example` (the gold label) and returns a dict LangSmith
understands: {"key": <metric name>, "score": <0-1 float>, "comment": <why>}.

Deterministic evaluators (router, tool selection, retrieval) need no LLM
call and are cheap to run on every PR. The two LLM-judge evaluators
(groundedness, correctness) cost a call per example -- run those on a
curated subset, not your full regression sweep, unless budget allows.
"""
from __future__ import annotations

import json

from metrics import best_iou, mean_iou, mrr, ndcg_at_k, recall_at_k

# ---------------------------------------------------------------------------
# 1. Router
# ---------------------------------------------------------------------------


def router_accuracy_evaluator(run, example) -> dict:
    predicted = run.outputs.get("needs_tool")
    expected = example.outputs.get("needs_tool")
    correct = predicted == expected
    return {
        "key": "router_accuracy",
        "score": 1.0 if correct else 0.0,
        "comment": f"predicted={predicted} expected={expected}",
    }


# Run this one separately over the whole suite to get precision/recall/F1
# per class, since a single per-example 0/1 score can't express a confusion
# matrix -- see run_evals.py's summarize_router_confusion().


# ---------------------------------------------------------------------------
# 2. Tool selection
# ---------------------------------------------------------------------------


def tool_selection_accuracy_evaluator(run, example) -> dict:
    predicted = run.outputs.get("tool")
    expected = example.outputs.get("tool")
    correct = predicted == expected
    return {
        "key": "tool_selection_accuracy",
        "score": 1.0 if correct else 0.0,
        "comment": f"predicted={predicted!r} expected={expected!r}",
    }


# ---------------------------------------------------------------------------
# 3. Retrieval (temporal IoU based)
# ---------------------------------------------------------------------------


def make_retrieval_evaluators(k_values=(1, 3, 5), iou_threshold: float = 0.5):
    """Returns a list of evaluator functions, one per (metric, k) pair, so
    LangSmith's experiment view shows recall_at_1, recall_at_3, ... as
    separate columns instead of one blended number."""

    evaluators = []

    for k in k_values:

        def recall_evaluator(run, example, _k=k) -> dict:
            windows = run.outputs.get("windows", [])
            gt = [tuple(w) for w in example.outputs.get("gt_windows", [])]
            score = recall_at_k(windows, gt, _k, iou_threshold)
            return {"key": f"recall_at_{_k}", "score": score}

        def precision_evaluator(run, example, _k=k) -> dict:
            from metrics import precision_at_k

            windows = run.outputs.get("windows", [])
            gt = [tuple(w) for w in example.outputs.get("gt_windows", [])]
            score = precision_at_k(windows, gt, _k, iou_threshold)
            return {"key": f"precision_at_{_k}", "score": score}

        evaluators.append(recall_evaluator)
        evaluators.append(precision_evaluator)

    def mean_iou_at_1_evaluator(run, example) -> dict:
        windows = run.outputs.get("windows", [])
        gt = [tuple(w) for w in example.outputs.get("gt_windows", [])]
        return {"key": "mean_iou_at_1", "score": mean_iou(windows, gt, k=1)}

    def mrr_evaluator(run, example) -> dict:
        windows = run.outputs.get("windows", [])
        gt = [tuple(w) for w in example.outputs.get("gt_windows", [])]
        return {"key": "mrr", "score": mrr(windows, gt, iou_threshold)}

    def ndcg_evaluator(run, example) -> dict:
        windows = run.outputs.get("windows", [])
        gt = [tuple(w) for w in example.outputs.get("gt_windows", [])]
        return {"key": "ndcg_at_5", "score": ndcg_at_k(windows, gt, k=5, iou_threshold=iou_threshold)}

    evaluators += [mean_iou_at_1_evaluator, mrr_evaluator, ndcg_evaluator]
    return evaluators


# ---------------------------------------------------------------------------
# 4. Fusion-heuristic diagnostic
#
# Not a pass/fail score -- a diagnostic evaluator to answer the question
# raised earlier: "does max(speech_sim, caption_sim) actually pick the
# better modality?" Run this over a dataset where BOTH modalities' results
# are available for the same query (i.e. run retrieval_target once per
# modality, then compare offline -- see run_evals.py's
# analyze_fusion_heuristic()).
# ---------------------------------------------------------------------------


def fusion_choice_correctness(
    speech_windows: list[tuple[float, float]],
    speech_sims: list[float],
    caption_windows: list[tuple[float, float]],
    caption_sims: list[float],
    gt_windows: list[tuple[float, float]],
    iou_threshold: float = 0.5,
) -> dict:
    """Given both modalities' top result for the same query, replay the
    current argmax(sim) heuristic and check whether it happened to pick
    the modality whose top-1 IoU against ground truth was actually higher."""
    speech_top = speech_windows[0] if speech_windows else None
    caption_top = caption_windows[0] if caption_windows else None
    speech_sim = speech_sims[0] if speech_sims else 0.0
    caption_sim = caption_sims[0] if caption_sims else 0.0

    heuristic_pick = "speech" if speech_sim > caption_sim else "caption"

    speech_iou = best_iou(speech_top, gt_windows) if speech_top else 0.0
    caption_iou = best_iou(caption_top, gt_windows) if caption_top else 0.0
    truly_better = "speech" if speech_iou > caption_iou else ("caption" if caption_iou > speech_iou else "tie")

    heuristic_correct = truly_better == "tie" or heuristic_pick == truly_better
    return {
        "heuristic_pick": heuristic_pick,
        "truly_better_modality": truly_better,
        "heuristic_correct": heuristic_correct,
        "speech_iou": speech_iou,
        "caption_iou": caption_iou,
    }


# ---------------------------------------------------------------------------
# 5. LLM-as-judge: groundedness / faithfulness
# ---------------------------------------------------------------------------

_GROUNDEDNESS_JUDGE_PROMPT = """You are checking whether an AI-generated answer is fully supported by the \
provided source context. The answer must not contain claims, names, numbers, or events that are not \
present in or directly inferable from the context.

Context (retrieved from the video):
{context}

Answer to check:
{answer}

Respond with ONLY a JSON object, no other text:
{{"grounded": true|false, "unsupported_claims": ["...", ...], "reasoning": "one sentence"}}"""


def make_groundedness_evaluator(judge_llm):
    """`judge_llm` should be a LangChain chat model instance (e.g. the same
    Anthropic client the project already uses via llm.py) -- pass one in
    rather than constructing it here so the eval harness doesn't hardcode a
    model version."""

    def groundedness_evaluator(run, example) -> dict:
        context = "\n".join(run.outputs.get("retrieved_context", []))
        answer = run.outputs.get("answer", "")
        prompt = _GROUNDEDNESS_JUDGE_PROMPT.format(context=context or "(no context returned)", answer=answer)

        response = judge_llm.invoke(prompt)
        text = response.content if hasattr(response, "content") else str(response)
        try:
            parsed = json.loads(text.strip().strip("```json").strip("```"))
        except json.JSONDecodeError:
            return {"key": "groundedness", "score": 0.0, "comment": f"judge did not return valid JSON: {text[:200]}"}

        return {
            "key": "groundedness",
            "score": 1.0 if parsed.get("grounded") else 0.0,
            "comment": parsed.get("reasoning", ""),
        }

    return groundedness_evaluator


# ---------------------------------------------------------------------------
# 6. LLM-as-judge: answer correctness against a reference answer
# ---------------------------------------------------------------------------

_CORRECTNESS_JUDGE_PROMPT = """You are grading whether a candidate answer conveys the same substantive \
information as a reference answer. Minor phrasing differences are fine; missing or contradictory facts are not.

Reference answer:
{reference}

Candidate answer:
{candidate}

Respond with ONLY a JSON object, no other text:
{{"score": <0-5 integer>, "reasoning": "one sentence"}}"""


def make_correctness_evaluator(judge_llm):
    def correctness_evaluator(run, example) -> dict:
        reference = example.outputs.get("reference_answer", "")
        candidate = run.outputs.get("answer", "")
        prompt = _CORRECTNESS_JUDGE_PROMPT.format(reference=reference, candidate=candidate)

        response = judge_llm.invoke(prompt)
        text = response.content if hasattr(response, "content") else str(response)
        try:
            parsed = json.loads(text.strip().strip("```json").strip("```"))
        except json.JSONDecodeError:
            return {"key": "answer_correctness", "score": 0.0, "comment": f"judge did not return valid JSON: {text[:200]}"}

        return {
            "key": "answer_correctness",
            "score": parsed.get("score", 0) / 5.0,
            "comment": parsed.get("reasoning", ""),
        }

    return correctness_evaluator


# ---------------------------------------------------------------------------
# 7. Rewrite-drift diagnostic (finalize.py risk)
#
# Compares the tool loop's raw output against finalize.py's polished
# rewrite, to isolate whether hallucination is introduced by the rewrite
# step specifically (see targets.e2e_target -- capture the pre-finalize
# AIMessage alongside the post-finalize one to use this).
# ---------------------------------------------------------------------------


def make_rewrite_drift_evaluator(judge_llm):
    prompt_template = """Compare these two versions of the same answer. Version B is a stylistic rewrite of \
Version A and should not introduce any new facts.

Version A (raw):
{raw}

Version B (rewritten):
{rewritten}

Respond with ONLY a JSON object, no other text:
{{"new_facts_introduced": true|false, "examples": ["...", ...]}}"""

    def rewrite_drift_evaluator(run, example) -> dict:
        raw = run.outputs.get("raw_answer", "")
        rewritten = run.outputs.get("answer", "")
        response = judge_llm.invoke(prompt_template.format(raw=raw, rewritten=rewritten))
        text = response.content if hasattr(response, "content") else str(response)
        try:
            parsed = json.loads(text.strip().strip("```json").strip("```"))
        except json.JSONDecodeError:
            return {"key": "rewrite_drift", "score": 0.0, "comment": f"judge did not return valid JSON: {text[:200]}"}

        introduced = parsed.get("new_facts_introduced", False)
        return {
            "key": "rewrite_drift",
            "score": 0.0 if introduced else 1.0,
            "comment": "; ".join(parsed.get("examples", [])),
        }

    return rewrite_drift_evaluator
