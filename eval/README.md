# Eval harness for multimodal-video-agent

This is a set of plain Python scripts, not a framework — nothing here is magic.
Every "target" function calls a real function from `multimodal_agent` or
`video_mcp_server` directly; every "evaluator" function is either simple math
(`metrics.py`) or one LLM call. LangSmith just orchestrates: for each labeled
example in a dataset, call the target, hand its output + the example's label
to each evaluator, record the scores. That's the whole mechanism, five times
over, once per suite.

## What each file actually does

**`metrics.py`** — pure math, zero project imports, zero LangSmith imports.
Temporal IoU, recall@k, precision@k, MRR, nDCG — all operating on plain
`(start, end)` second tuples. This file doesn't know LangSmith or your agent
exist. You can `import metrics` and unit test it on its own, which is why it's
separated out — if a retrieval score looks wrong, first check whether the bug
is in `metrics.py`'s arithmetic or in `targets.py`'s data plumbing, and this
split makes that fast to isolate.

**`schemas.py`** — typed builder functions (`router_example(...)`,
`retrieval_example(...)`, etc.) that produce the `{"inputs": ..., "outputs":
...}` dicts LangSmith datasets are made of. No behavior, just shape
enforcement so `seed_datasets.py` can't accidentally write a malformed
example that silently breaks a target or evaluator later. If you add a 6th
suite, add its builder here first.

**`targets.py`** — the only file that imports your actual project code
(`multimodal_agent.agent...`, `video_mcp_server.video...`). Each `*_target`
function is "the thing being evaluated," wired to call the real code path,
not a reimplementation:
- `router_target` builds the real `router_node` (real `build_routing_llm()`,
  real `routing_system_prompt()` pulled live from LangSmith) and calls it.
- `tool_selection_target` binds the real MCP tools to the real tool-use LLM
  and reads off the first tool call — same LLM call `tool_agent_node` makes,
  stopping short of actually executing the tool.
- `retrieval_target` calls `VideoSearchEngine.search_by_speech` /
  `search_by_caption` / `search_by_image` directly against Pixeltable.
- `qa_target` calls `get_caption_info` directly — the same retrieval
  `ask_question_about_video` uses.
- `e2e_target` builds and invokes the full compiled LangGraph, same as
  `api.py` does for a real chat turn.

Each function takes one example's `inputs` dict, returns an `outputs` dict.
That's the entire contract LangSmith needs.

**`evaluators.py`** — scores what a target produced against what the example
said it should be. Two kinds:
- *Deterministic* (`router_accuracy_evaluator`, `tool_selection_accuracy_evaluator`,
  everything from `make_retrieval_evaluators`) — plain comparison or a call
  into `metrics.py`. No LLM call, free, instant, deterministic.
- *LLM-as-judge* (`make_groundedness_evaluator`, `make_correctness_evaluator`,
  `make_rewrite_drift_evaluator`) — these take a `judge_llm` argument (a
  LangChain chat model instance) and prompt it to grade the target's output.
  One extra LLM call per example, per evaluator. Costs money, isn't fully
  deterministic across runs (temperature/model updates can shift scores
  slightly), which is exactly why the cheap deterministic suites exist
  separately — you don't want every PR paying for judge calls.

Two diagnostic evaluators (`fusion_choice_correctness` and `make_rewrite_drift_evaluator`)
are also wired into `run_evals.py` — see "Diagnostic Evaluators" below.

**`seed_datasets.py`** — one-time (or ongoing) script that creates the 5
LangSmith datasets and populates them with examples via `schemas.py`'s
builders. This is where **your manual labeling work lives**. Run it again
any time you add examples — `client.create_examples` is additive, it won't
duplicate a dataset that already exists (checked via `_create_or_get`).

**`run_evals.py`** — the entry point. Wires each target to its evaluators and
calls `langsmith.evaluate(...)`, which does the loop-over-dataset-and-score
work. `python run_evals.py <suite>` runs one; `python run_evals.py all` runs
all five in sequence, suite by suite (not in parallel — see cost note below).

**`requirements.txt` / `.env.example`** — eval-only Python deps and the env
vars targets.py's imports need at runtime (`GROQ_API_KEY` for the LLMs,
`OPENAI_API_KEY` for Pixeltable's embedding/captioning calls that
`retrieval_target`/`qa_target` trigger, `LANGSMITH_API_KEY` for the eval
tracking itself).

## What needs to be running, per suite

| Suite | Needs `video-mcp-server` running? | Needs `postgres` running? | Needs a pre-indexed video? |
|---|---|---|---|
| `router` | No | No | No |
| `tool_selection` | No | No | No |
| `retrieval` | No — talks to Pixeltable directly | No | **Yes** |
| `qa` | No — talks to Pixeltable directly | No | **Yes** |
| `e2e` | **Yes** | **Yes** | **Yes** |

`router` and `tool_selection` only exercise LLM reasoning over text — no
video, no database, no other service. You can run those with nothing else
up at all, as long as `GROQ_API_KEY` is set.

`retrieval` and `qa` call `VideoSearchEngine` directly against Pixeltable's
on-disk store (`.pixeltable/`), bypassing the MCP server's HTTP layer
entirely — `targets.py` imports `video_mcp_server.video.video_search_service`
as a library, not as a client of the running service. So these two don't need
`video-mcp-server` *running*, but they do need the video to already be
**indexed into that same Pixeltable store** (see next section for why).

`e2e` is the only suite that needs live infrastructure, because it goes
through the real `setup_mcp()` → `MultiServerMCPClient` → HTTP connection to
`video-mcp-server`, and `build_graph()` needs a real Postgres-backed
checkpointer:

```bash
docker-compose up -d video-mcp-server postgres
python run_evals.py e2e
```

`python run_evals.py all` runs all five suites in one process, in the order
`router → tool_selection → retrieval → qa → e2e` — which means **it also
needs `video-mcp-server` and `postgres` up**, even though 4 of the 5 suites
don't individually require them, because the `e2e` suite at the end does.
Bring both up before running `all`, or just run the first four suites
individually and skip `e2e` if you don't want the containers up.

## Why isn't the video indexed automatically as part of the eval run?

Because indexing is a separate, expensive, slow pipeline — and mixing it
into eval would make every eval run test two unrelated things at once.

Indexing a video (the `process_video` MCP tool, deliberately excluded from
`tool_selection_target`'s tool list) means: extracting frames, running
speech-to-text over the full audio track, generating a caption per sampled
frame via a vision model, embedding every speech segment and every caption
and every frame — all real API calls to OpenAI, all taking real minutes per
video of footage, not milliseconds. If `retrieval_target` triggered that
pipeline on every call, a 10-example retrieval suite would take as long as
indexing 10 videos from scratch, cost accordingly, and — worse — you'd be
indexing the *same* video repeatedly every time you re-ran the suite, since
nothing here checks "is this video already indexed."

More importantly, it would conflate two different things you want to test
independently:
- **"Is the video-processing pipeline working?"** (frame extraction, ASR
  accuracy, captioning quality, embedding correctness) — a data-pipeline
  concern.
- **"Given a correctly-indexed video, does retrieval find the right
  moment?"** (the actual thing `retrieval-eval` and `qa-eval` are meant to
  isolate).

If both ran together, a retrieval score drop after a code change couldn't
tell you whether the change broke retrieval logic or just hit a transient
ASR/captioning API issue during re-indexing. Keeping the index as a fixed,
already-built precondition means retrieval scores are comparable
run-over-run — same input data, only the retrieval code under test changes.

**What this means for you in practice**: process your test videos through
the normal app flow once (upload → `process_video` runs → it lands in
Pixeltable) before writing `retrieval-eval`/`qa-eval` examples, note the
resulting `video_path`, and reuse that same indexed video across every
eval run from then on. Re-index only if you deliberately want to test the
processing pipeline itself, or if the video's index gets wiped. If you want,
I can add a small `eval/index_test_videos.py` script that calls
`process_video` once per video in a fixed list and waits for it to finish,
so this step is scripted rather than "go click through the UI" — say the
word and I'll write it.

## Setup

```bash
cd eval
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e ../multimodal_agent -e ../video_mcp_server

cp .env.example .env   # then fill in GROQ_API_KEY, OPENAI_API_KEY, LANGSMITH_API_KEY
export $(cat .env | xargs)
```

Runs on the host, not in a container — it imports both packages directly and
calls their internals as Python objects (`router_node(state)`,
`engine.search_by_speech(...)`), so it needs both on the same `sys.path`
rather than living behind either service's container boundary.

## 1. Seed the datasets

```bash
python seed_datasets.py
```

Creates the 5 LangSmith datasets and fills them with **placeholder**
examples — replace `VIDEO_PATH` and the timestamp windows with real labeled
data from your own indexed test videos. The placeholders exist to show the
labeling pattern, especially:

- the ambiguous `"show me where he says X"` vs `"what does he say about X"`
  pair in `tool-selection-eval` — exactly the case `TOOL_USE_SYSTEM_PROMPT`
  currently doesn't disambiguate
- multiple valid ground-truth windows per query in `retrieval-eval` (a line
  can be said more than once)

Add more examples over time by editing `seed_datasets.py` or directly in the
LangSmith UI's Datasets & Testing tab.

## 1.5. Index test videos (retrieval / qa suites only)

`retrieval` and `qa` talk to Pixeltable directly — no running MCP server
needed — but the video must already be indexed.  Run this once per test
video before you run those suites for the first time:

```bash
python index_test_videos.py
```

The script (see `index_test_videos.py`) calls `process_video()` for every
path listed in `VIDEOS_TO_INDEX`, which mirrors `seed_datasets.py`'s
`VIDEO_PATH` constant.  It is **idempotent** — re-running it when the video
is already indexed is a no-op.  Pass paths on the CLI to index a different
set of videos without editing the file:

```bash
python index_test_videos.py shared_media/my_other_video.mp4
```

> [!IMPORTANT]
> The video file must exist at the path before running the script.
> Place it under `shared_media/` in the project root (or wherever
> `video_mcp_server`'s `SHARED_MEDIA_DIR` points).

## 2. Run

```bash
python run_evals.py router            # single suite, fast iteration, no infra needed
python run_evals.py tool_selection    # single suite, fast iteration, no infra needed
python run_evals.py retrieval         # needs pre-indexed video(s), no running services
python run_evals.py qa                # needs pre-indexed video(s), no running services
python run_evals.py fusion            # multi-modal heuristic analysis against ground truth
python run_evals.py e2e               # needs video-mcp-server + postgres up
python run_evals.py all               # runs all suites and diagnostics in sequence
```


Results show up as LangSmith **experiments** attached to each dataset —
that's what you get back on a successful run: not a pass/fail exit code, but
a browsable table in the LangSmith UI (and returned in Python as the
`evaluate()` result object) with one row per example, each example's target
output, each evaluator's score + comment, and aggregate stats across the
run. Re-running the same suite creates a new experiment under the same
dataset, so you compare experiments side-by-side across commits or prompt
versions rather than only ever seeing the latest number.

## Diagnostic Evaluators

- **`fusion_choice_correctness`** (`evaluators.py` / `python run_evals.py fusion`) —
  evaluates `get_video_clip_from_user_query`'s `max(speech_sim, caption_sim)`
  heuristic against ground-truth windows. For each query in `retrieval-eval`,
  it executes `retrieval_target` across both speech and caption modalities,
  then computes whether the heuristic picked the modality that achieved higher
  temporal IoU against ground truth. It prints a breakdown per query and an
  aggregate summary showing how often the heuristic was optimal vs suboptimal.
  Worth running before spending time tuning either retriever individually.
- **`make_rewrite_drift_evaluator`** (`evaluators.py` / wired into `e2e` suite) —
  compares `finalize.py`'s rewritten answer against the raw tool-loop output (`raw_answer`)
  to isolate hallucination introduced specifically by the rewrite step.
  Scores 1.0 if no new unsupported facts were introduced during finalization,
  or 0.0 if the LLM judge detected hallucinated details.