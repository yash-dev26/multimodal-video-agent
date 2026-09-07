"""
E1, E2: the two most important real user journeys in the product, run
against the REAL, full docker-compose stack (see .github/workflows/e2e.yml)
-- real Groq LLM calls, real OpenAI transcription/embeddings, real CLIP
embeddings, real ffmpeg clip extraction. No fakes anywhere in this file.

Both tests share ONE uploaded+processed video (see `processed_video`
below, session-scoped) since ingestion cost/time dominates -- re-uploading
per test would roughly double real API spend and CI runtime for no
additional signal.

Fixture video (fixtures/fixture_video.mp4, ~8s, ~70KB, generated with
ffmpeg + espeak-ng -- see the comment block at the bottom of this file for
the exact generation commands, in case it ever needs regenerating):
  - 0:00-0:04  solid RED frame (320x240). Audio: "The secret code word is
               pineapple. I repeat, the secret code word is pineapple."
  - 0:04-0:08  solid BLUE frame (320x240). Silent.

Fixture image (fixtures/query_frame.png): a plain solid-red 320x240 PNG,
pixel-identical in hue to the video's red segment -- used as the
image-search query in E2. Verified by extracting real frames from the
fixture at t=1s (red, RGB ~(253,0,0)) and t=6s (blue, RGB ~(0,0,254)) and
comparing against this image's pixel value during fixture creation.
"""

from __future__ import annotations

import base64
import time
from pathlib import Path

import httpx
import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"
FIXTURE_VIDEO = FIXTURES_DIR / "fixture_video.mp4"
QUERY_IMAGE = FIXTURES_DIR / "query_frame.png"

# Real ingestion (transcription + frame captioning + two embedding passes)
# on even an 8s video can take a couple of minutes depending on model
# cold-start latency -- generous but bounded so a genuinely stuck task
# still fails the job instead of hanging until the workflow's own
# `timeout-minutes: 30` kills it with a less specific error.
TASK_POLL_TIMEOUT_SECONDS = 300
TASK_POLL_INTERVAL_SECONDS = 5


def _poll_until_settled(client: httpx.Client, task_id: str) -> str:
    elapsed = 0
    while elapsed < TASK_POLL_TIMEOUT_SECONDS:
        resp = client.get(f"/task-status/{task_id}")
        resp.raise_for_status()
        status = resp.json()["status"]
        if status in ("completed", "failed"):
            return status
        time.sleep(TASK_POLL_INTERVAL_SECONDS)
        elapsed += TASK_POLL_INTERVAL_SECONDS
    raise AssertionError(f"Task {task_id} did not settle within {TASK_POLL_TIMEOUT_SECONDS}s")


@pytest.fixture(scope="session")
def processed_video(client: httpx.Client) -> str:
    """Uploads and fully indexes the fixture video ONCE per test session --
    exercising the real upload -> process -> poll-to-completion journey --
    and reuses the resulting index across both E1 and E2 below.
    """
    assert FIXTURE_VIDEO.exists(), f"Missing fixture video at {FIXTURE_VIDEO}"

    with open(FIXTURE_VIDEO, "rb") as f:
        upload_resp = client.post("/upload-video", files={"file": ("e2e_fixture.mp4", f, "video/mp4")})
    upload_resp.raise_for_status()
    video_path = upload_resp.json()["video_path"]

    process_resp = client.post("/process-video", json={"video_path": video_path})
    process_resp.raise_for_status()
    task_id = process_resp.json()["task_id"]

    status = _poll_until_settled(client, task_id)
    assert status == "completed", (
        f"Fixture video failed to process (status={status}) -- check the "
        f"video-mcp-server container logs for the real ingestion error."
    )

    return video_path


def test_speech_query_end_to_end(client: httpx.Client, processed_video: str):
    """E1: the single most important real user journey -- upload, process,
    ask a question whose answer only exists in a known spoken phrase, and
    get back a real, playable clip.

    Exercises the full real stack with no fakes: OpenAI transcription,
    text-embedding similarity search, Groq routing/tool-selection, ffmpeg
    clip extraction, and the /media serving path.
    """
    chat_resp = httpx_client_post_chat(
        client,
        message="What is the secret code word mentioned in the video?",
        video_path=processed_video,
    )
    body = chat_resp.json()

    assert body["clip_path"], f"Expected a clip_path in the response, got: {body}"
    assert "pineapple" in body["message"].lower(), (
        f"Expected the answer to mention the actual spoken code word "
        f"('pineapple'), got: {body['message']!r}"
    )

    _assert_clip_is_playable(client, body["clip_path"])


def test_image_query_end_to_end(client: httpx.Client, processed_video: str):
    """E2: image-similarity search -- the only test in the whole suite
    (unit + integration + E2E) that exercises search_by_image / the real
    CLIP embedding path, since the integration suite's I3 only covers the
    text-query path against a fake MCP server.
    """
    assert QUERY_IMAGE.exists(), f"Missing query image at {QUERY_IMAGE}"
    image_b64 = base64.b64encode(QUERY_IMAGE.read_bytes()).decode("ascii")

    chat_resp = httpx_client_post_chat(
        client,
        message="Find the moment in the video that looks like this image.",
        video_path=processed_video,
        image_base64=image_b64,
    )
    body = chat_resp.json()

    assert body["clip_path"], f"Expected a clip_path in the response, got: {body}"
    _assert_clip_is_playable(client, body["clip_path"])


def httpx_client_post_chat(client: httpx.Client, **payload) -> httpx.Response:
    resp = client.post("/chat", json=payload)
    resp.raise_for_status()
    return resp


def _assert_clip_is_playable(client: httpx.Client, clip_path: str) -> None:
    clip_filename = Path(clip_path).name
    media_resp = client.get(f"/media/{clip_filename}")
    assert media_resp.status_code == 200, f"GET /media/{clip_filename} returned {media_resp.status_code}"
    assert len(media_resp.content) > 1000, "Clip file is suspiciously small/empty -- likely a broken extraction"


# ---------------------------------------------------------------------------
# Fixture regeneration -- for reference only, not executed by pytest.
#
# If fixtures/fixture_video.mp4 or query_frame.png ever need to be
# regenerated (e.g. to use a different phrase or color), these are the
# exact commands used to build them (requires ffmpeg + espeak-ng):
#
#   espeak-ng -s 130 -w speech.wav \
#     "The secret code word is pineapple. I repeat, the secret code word is pineapple."
#   ffmpeg -f lavfi -i anullsrc=r=24000:cl=mono -t 0.5 silence.wav
#   printf "file 'silence.wav'\nfile 'speech.wav'\nfile 'silence.wav'\n" > concat_list.txt
#   ffmpeg -f concat -safe 0 -i concat_list.txt -c copy padded_speech.wav
#
#   ffmpeg -f lavfi -i "color=c=red:s=320x240:d=4:r=10" \
#          -f lavfi -i "color=c=blue:s=320x240:d=4:r=10" \
#          -filter_complex "[0:v][1:v]concat=n=2:v=1:a=0[v]" -map "[v]" \
#          -pix_fmt yuv420p video_only.mp4
#   ffmpeg -i video_only.mp4 -i padded_speech.wav \
#          -filter_complex "[1:a]apad[a]" -map 0:v -map "[a]" \
#          -c:v libx264 -c:a aac -shortest -t 8 fixture_video.mp4
#
#   ffmpeg -f lavfi -i "color=c=red:s=320x240:d=0.1" -frames:v 1 query_frame.png
# ---------------------------------------------------------------------------
