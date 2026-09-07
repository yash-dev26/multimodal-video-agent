"""
I10: regression guard for the P1 bug where a single module-level
VideoProcessor instance was shared across concurrent process_video()
calls, letting one video's setup_table()/add_video() clobber another's
in-flight instance state (self.pxt_cache, self.video_table, ...).

The fix makes process_video() construct a fresh VideoProcessor per call
(see tools.py). This test proves that invariant holds by monkeypatching
VideoProcessor.setup_table/add_video to record `id(self)` and their
video_name argument, then running two calls concurrently and asserting
each used its OWN instance for its OWN video, never crossing over.

No real Pixeltable/ffmpeg/OpenAI work happens -- setup_table/add_video are
fully replaced -- so this stays fast and free while still exercising the
REAL process_video() function and real VideoProcessor instance identity.
"""

import asyncio
import os
import threading
import time

os.environ.setdefault("OPENAI_API_KEY", "test-placeholder")
os.environ.setdefault("LANGSMITH_API_KEY", "test-placeholder")
os.environ.setdefault("LANGSMITH_TRACING", "false")

import pytest

from video_mcp_server.tools import process_video
from video_mcp_server.video.ingestion.video_processor import VideoProcessor


@pytest.mark.asyncio
async def test_concurrent_process_video_calls_use_isolated_instances(monkeypatch):
    instance_log: list[tuple[int, str]] = []
    log_lock = threading.Lock()

    def fake_check_if_exists(self, video_path: str) -> bool:
        return False  # force every call down the "needs processing" path

    def fake_setup_table(self, video_name: str) -> None:
        with log_lock:
            instance_log.append((id(self), video_name))
        # Simulate ingestion taking real time so any concurrent calls'
        # setup_table() invocations actually overlap in wall time --
        # without this, sequential-by-luck execution would prove nothing.
        time.sleep(0.05)
        self._video_name_under_setup = video_name  # mimics real per-instance state

    def fake_add_video(self, video_path: str) -> bool:
        # If VideoProcessor were still a shared singleton, this assertion
        # would fail: a second concurrent call's setup_table() could have
        # overwritten self._video_name_under_setup between THIS instance's
        # setup_table() and add_video() calls.
        assert getattr(self, "_video_name_under_setup", None) == video_path, (
            "This VideoProcessor instance's state was mutated by a "
            "DIFFERENT concurrent call -- VideoProcessor is being shared "
            "again instead of instantiated per-call in process_video()."
        )
        return True

    monkeypatch.setattr(VideoProcessor, "_check_if_exists", fake_check_if_exists)
    monkeypatch.setattr(VideoProcessor, "setup_table", fake_setup_table)
    monkeypatch.setattr(VideoProcessor, "add_video", fake_add_video)

    results = await asyncio.gather(
        asyncio.to_thread(process_video, "shared_media/video_a.mp4"),
        asyncio.to_thread(process_video, "shared_media/video_b.mp4"),
    )

    assert results == [True, True]

    # Each recorded (instance_id, video_name) pair must be unique per
    # video -- if the two calls shared one VideoProcessor, both entries
    # would show the SAME instance id.
    instance_ids = [entry[0] for entry in instance_log]
    assert len(set(instance_ids)) == 2, (
        f"Expected 2 distinct VideoProcessor instances, got instance ids "
        f"{instance_ids} -- process_video() is sharing a VideoProcessor "
        f"across concurrent calls again."
    )

    video_names_by_instance = dict(instance_log)
    assert video_names_by_instance[instance_ids[0]] != video_names_by_instance[instance_ids[1]]
