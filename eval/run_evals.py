"""
Runs all eval suites via langsmith.evaluate(). Each suite is independent --
run them individually while iterating (`python run_evals.py router`), or
all together as a regression gate (`python run_evals.py all`).

Suite -> approx cost/latency, so you can decide what runs per-PR vs
pre-release:
    router          cheap, 1 LLM call/example    -> every PR
    tool_selection  cheap, 1 LLM call/example    -> every PR
    retrieval       cheap, no LLM call           -> every PR
    qa              1 judge call/example         -> every PR (small dataset)
    e2e             2-4 LLM calls/example        -> pre-release / nightly
"""
from __future__ import annotations

import sys
import dotenv

dotenv.load_dotenv()  # load GROQ_API_KEY from .env if present


from langsmith import evaluate

from evaluators import (
    fusion_choice_correctness,
    make_correctness_evaluator,
    make_groundedness_evaluator,
    make_retrieval_evaluators,
    make_rewrite_drift_evaluator,
    router_accuracy_evaluator,
    tool_selection_accuracy_evaluator,
)
from targets import e2e_target, qa_target, retrieval_target, router_target, tool_selection_target


def _judge_llm():
    # Reuse the project's own LLM builder (ChatGroq, see llm.py) so the
    # judge is configured the same way (GROQ_API_KEY, base settings) as the
    # rest of the agent. Worth swapping for a different provider/model if
    # you want the judge to not share failure modes with the model being
    # graded -- e.g. a Groq model judging a Groq model's own hallucinations
    # is weaker evidence than an independent judge would be.
    from multimodal_agent.agent.llm import build_finalize_llm

    return build_finalize_llm()


def run_router_suite():
    return evaluate(
        router_target,
        data="router-eval",
        evaluators=[router_accuracy_evaluator],
        experiment_prefix="router",
        # Groq on-demand tier is capped at 8 000 TPM for this model;
        # serialise requests to avoid 429s.
        max_concurrency=1,
    )


def run_tool_selection_suite():
    return evaluate(
        tool_selection_target,
        data="tool-selection-eval",
        evaluators=[tool_selection_accuracy_evaluator],
        experiment_prefix="tool-selection",
        # Groq on-demand tier is capped at 8 000 TPM for this model;
        # serialise requests to avoid 429s.
        max_concurrency=1,
    )


def _prepare_pixeltable() -> None:
    """Pre-start Pixeltable's embedded postgres in the main thread.

    **Root cause on Windows**: After a previous python process exits,
    pixeltable_pgserver's atexit ``_cleanup()`` kills the postgres
    process via ``process.terminate()`` / ``process.kill()`` instead
    of a clean ``pg_ctl stop``.  This leaves the pgdata control file
    in "interrupted" state, which means the next startup requires
    crash recovery.  During crash recovery postgres tries to open
    ``pgdata/log`` for writing — but ``pg_ctl start -l pgdata/log``
    has already opened that file, and on Windows that produces a
    "sharing violation", causing crash recovery (and therefore startup)
    to fail within the 10-second subprocess timeout.

    **Fix** (two steps):

    1. Run ``pg_resetwal -f`` on pgdata to mark it as cleanly shut
       down.  This removes the crash-recovery requirement entirely, so
       postgres starts without ever touching ``pgdata/log`` during
       recovery.  The actual data (video embeddings etc.) is intact; only
       the WAL control file status byte is updated.

    2. Delete the stale ``pgdata/log`` file so ``pg_ctl start`` creates
       a fresh one without a pre-existing handle conflict.

    3. Call ``pxt.list_tables()`` (main thread, before any LangSmith
       worker thread runs) so ``PostgresServer._postmaster_info`` is
       populated before workers call ``Env.get()``.
    """
    import pathlib
    import subprocess

    pgdata = pathlib.Path.home() / ".pixeltable" / "pgdata"
    pg_resetwal = (
        pathlib.Path(__file__).parent.parent  # eval/ -> repo root
        / ".venv" / "Lib" / "site-packages"
        / "pixeltable_pgserver" / "pginstall" / "bin" / "pg_resetwal.exe"
    )

    # Step 1: Reset WAL so postgres treats pgdata as cleanly shut down.
    if pgdata.exists() and pg_resetwal.exists():
        try:
            # Kill any lingering postgres processes first so pg_resetwal
            # doesn't refuse with "server appears to be running".
            import psutil
            for proc in psutil.process_iter(attrs=["name", "cmdline"]):
                if proc.info["name"] == "postgres":
                    cmdline = proc.info.get("cmdline") or []
                    if any(str(pgdata) in arg for arg in cmdline):
                        proc.kill()
        except Exception:
            pass

        try:
            subprocess.run(
                [str(pg_resetwal), "-f", str(pgdata)],
                capture_output=True,
                timeout=30,
            )
        except Exception:
            pass  # if pg_resetwal fails, fall through and let pixeltable try

    # Step 2: Remove the stale log file so pg_ctl can create a fresh one.
    log_file = pgdata / "log"
    try:
        log_file.unlink(missing_ok=True)
    except OSError:
        pass

    # Step 3: Initialize Pixeltable (starts postgres) in the main thread
    # before LangSmith spawns any worker threads.
    import pixeltable as pxt  # deferred: slow import, only needed for retrieval/qa
    try:
        pxt.list_tables()  # any catalog call forces full initialization
    except Exception:
        pass  # surface errors in target functions with full tracebacks



def run_retrieval_suite():
    _prepare_pixeltable()
    return evaluate(
        retrieval_target,
        data="retrieval-eval",
        evaluators=make_retrieval_evaluators(k_values=(1, 3, 5), iou_threshold=0.5),
        experiment_prefix="retrieval",
        # Run sequentially: Pixeltable uses process-global state
        # (_postmaster_info) that must be set before any worker thread
        # calls Env.get(). _prepare_pixeltable() handles the main-thread
        # init; max_concurrency=1 keeps workers from racing on it.
        max_concurrency=1,
    )


def run_qa_suite():
    _prepare_pixeltable()
    judge = _judge_llm()
    return evaluate(
        qa_target,
        data="qa-eval",
        evaluators=[make_groundedness_evaluator(judge), make_correctness_evaluator(judge)],
        experiment_prefix="qa",
        # Same Pixeltable prep requirement as retrieval.
        max_concurrency=1,
    )


def run_e2e_suite():
    judge = _judge_llm()
    return evaluate(
        e2e_target,
        data="e2e-eval",
        evaluators=[make_correctness_evaluator(judge), make_rewrite_drift_evaluator(judge)],
        experiment_prefix="e2e",
    )


def summarize_router_confusion(results) -> None:
    """LangSmith's per-example scores don't give you a confusion matrix
    directly -- pull predicted/expected back out of the comment field and
    print one. Router false negatives (missed a real tool need) matter
    more than false positives -- flag them separately."""
    tp = fp = tn = fn = 0
    for r in results:
        for eval_result in r.get("evaluation_results", {}).get("results", []):
            if eval_result.key != "router_accuracy":
                continue
            predicted = "predicted=True" in eval_result.comment
            expected = "expected=True" in eval_result.comment
            if predicted and expected:
                tp += 1
            elif predicted and not expected:
                fp += 1
            elif not predicted and expected:
                fn += 1
            else:
                tn += 1
    print(f"Router confusion: TP={tp} FP={fp} TN={tn} FN={fn}")
    if fn:
        print(f"  -> {fn} case(s) where a real tool need was missed -- check these first.")


def analyze_fusion_heuristic() -> dict:
    """Evaluates get_video_clip_from_user_query's argmax(speech_sim, caption_sim)
    heuristic against ground-truth windows across all text retrieval examples.
    Runs speech and caption retrieval for each query and compares which modality
    actually had a higher IoU against ground truth.
    """
    from langsmith import Client

    client = Client()
    examples = list(client.list_examples(dataset_name="retrieval-eval"))
    if not examples:
        print("No examples found in 'retrieval-eval' dataset.")
        return {}

    total = 0
    correct = 0
    ties = 0
    incorrect = 0

    print(f"\n--- Analyzing Fusion Heuristic ({len(examples)} candidate examples) ---")
    seen_queries = set()

    for eg in examples:
        inputs = eg.inputs
        outputs = eg.outputs or {}
        modality = inputs.get("modality")
        if modality not in ("speech", "caption"):
            continue

        query = inputs.get("query")
        video_path = inputs.get("video_path")
        pair_key = (video_path, query)
        if pair_key in seen_queries:
            continue
        seen_queries.add(pair_key)

        gt_windows = [tuple(w) for w in outputs.get("gt_windows", [])]
        speech_out = retrieval_target({**inputs, "modality": "speech"})
        caption_out = retrieval_target({**inputs, "modality": "caption"})

        res = fusion_choice_correctness(
            speech_windows=speech_out.get("windows", []),
            speech_sims=speech_out.get("similarities", []),
            caption_windows=caption_out.get("windows", []),
            caption_sims=caption_out.get("similarities", []),
            gt_windows=gt_windows,
        )

        total += 1
        if res["truly_better_modality"] == "tie":
            ties += 1
        elif res["heuristic_correct"]:
            correct += 1
        else:
            incorrect += 1

        q_repr = repr(query)[:40]
        print(
            f"Query: {q_repr:<42} "
            f"Pick: {res['heuristic_pick']:<7} "
            f"Best: {res['truly_better_modality']:<7} "
            f"Speech IoU: {res['speech_iou']:.2f} "
            f"Caption IoU: {res['caption_iou']:.2f} "
            f"Match: {'✓' if res['heuristic_correct'] else '✗'}"
        )

    acc = (correct / (total - ties)) if (total - ties) > 0 else 1.0
    overall_acc = (correct + ties) / total if total > 0 else 1.0
    print("\n=== Fusion Heuristic Summary ===")
    print(f"Total evaluated: {total} (Ties: {ties})")
    print(f"Heuristic correct: {correct} / {total - ties} non-tied cases ({acc * 100:.1f}%)")
    print(f"Overall (including ties as non-harmful): {overall_acc * 100:.1f}%")
    if incorrect > 0:
        print(f"  -> In {incorrect} case(s), the heuristic chose the lower-IoU modality.")

    return {
        "total": total,
        "correct": correct,
        "ties": ties,
        "incorrect": incorrect,
        "accuracy_excluding_ties": acc,
        "overall_accuracy": overall_acc,
    }


SUITES = {
    "router": run_router_suite,
    "tool_selection": run_tool_selection_suite,
    "retrieval": run_retrieval_suite,
    "qa": run_qa_suite,
    "e2e": run_e2e_suite,
    "fusion": analyze_fusion_heuristic,
}


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which == "all":
        for name, fn in SUITES.items():
            print(f"\n=== Running {name} suite ===")
            fn()
    elif which in SUITES:
        SUITES[which]()
    else:
        print(f"Unknown suite '{which}'. Options: all, {', '.join(SUITES)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
