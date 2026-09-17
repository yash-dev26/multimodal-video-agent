"""
Pure, dependency-free metric functions for video moment retrieval.

These operate on plain (start, end) second tuples so they can be unit
tested on their own, independent of LangSmith, Pixeltable, or the agent
graph. Everything in evaluators.py is a thin LangSmith wrapper around
these.
"""
from __future__ import annotations

import math
from typing import Sequence

Window = tuple[float, float]


def temporal_iou(pred: Window, gt: Window) -> float:
    """Intersection-over-union between two (start, end) second windows."""
    p_start, p_end = pred
    g_start, g_end = gt
    inter_start = max(p_start, g_start)
    inter_end = min(p_end, g_end)
    intersection = max(0.0, inter_end - inter_start)

    union_start = min(p_start, g_start)
    union_end = max(p_end, g_end)
    union = union_end - union_start
    if union <= 0:
        return 0.0
    return intersection / union


def best_iou(pred: Window, gt_windows: Sequence[Window]) -> float:
    """Max IoU of `pred` against any of several acceptable ground-truth windows
    (a query can have more than one valid moment -- e.g. a line said twice)."""
    if not gt_windows:
        return 0.0
    return max(temporal_iou(pred, gt) for gt in gt_windows)


def boundary_error(pred: Window, gt_windows: Sequence[Window]) -> dict:
    """Signed start/end offset (seconds) against whichever gt window best matches."""
    if not gt_windows:
        return {"start_err": None, "end_err": None}
    gt = max(gt_windows, key=lambda w: temporal_iou(pred, w))
    return {"start_err": pred[0] - gt[0], "end_err": pred[1] - gt[1]}


def recall_at_k(
    retrieved: Sequence[Window],
    gt_windows: Sequence[Window],
    k: int,
    iou_threshold: float = 0.5,
) -> float:
    """1.0 if any of the top-k retrieved windows overlaps a gt window at
    >= iou_threshold, else 0.0. This is the standard binary-relevance
    R@k used in moment-retrieval papers -- average it across queries to
    get the dataset-level R@k."""
    top_k = retrieved[:k]
    return 1.0 if any(best_iou(w, gt_windows) >= iou_threshold for w in top_k) else 0.0


def precision_at_k(
    retrieved: Sequence[Window],
    gt_windows: Sequence[Window],
    k: int,
    iou_threshold: float = 0.5,
) -> float:
    top_k = retrieved[:k]
    if not top_k:
        return 0.0
    relevant = sum(1 for w in top_k if best_iou(w, gt_windows) >= iou_threshold)
    return relevant / len(top_k)


def mean_iou(retrieved: Sequence[Window], gt_windows: Sequence[Window], k: int = 1) -> float:
    """Mean IoU of the top-k retrieved windows against the best-matching gt window.
    Use k=1 to score "the clip we'd actually show the user"."""
    top_k = retrieved[:k]
    if not top_k:
        return 0.0
    return sum(best_iou(w, gt_windows) for w in top_k) / len(top_k)


def mrr(
    retrieved: Sequence[Window],
    gt_windows: Sequence[Window],
    iou_threshold: float = 0.5,
) -> float:
    """Reciprocal rank of the first retrieved window that clears iou_threshold."""
    for rank, w in enumerate(retrieved, start=1):
        if best_iou(w, gt_windows) >= iou_threshold:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(
    retrieved: Sequence[Window],
    gt_windows: Sequence[Window],
    k: int,
    iou_threshold: float = 0.5,
) -> float:
    """Binary-relevance nDCG@k (relevance = 1 if IoU >= threshold else 0)."""
    top_k = retrieved[:k]

    def dcg(rels: Sequence[int]) -> float:
        return sum(rel / math.log2(i + 2) for i, rel in enumerate(rels))

    rels = [1 if best_iou(w, gt_windows) >= iou_threshold else 0 for w in top_k]
    ideal_rels = sorted(rels, reverse=True)
    ideal = dcg(ideal_rels)
    if ideal == 0:
        return 0.0
    return dcg(rels) / ideal
