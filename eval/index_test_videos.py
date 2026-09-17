"""
One-time setup helper: index the test videos needed by ``retrieval`` and
``qa`` eval suites into Pixeltable so those suites can run offline.

Usage
-----
    # From the eval/ directory, with the venv active:
    python index_test_videos.py

Add any additional video paths to VIDEOS_TO_INDEX below.  Each path should
be the same string that appears in the LangSmith dataset examples (i.e. the
value of ``video_path`` in ``seed_datasets.py``), which is relative to
``video_mcp_server``'s ``SHARED_MEDIA_DIR``.

The script is intentionally idempotent: ``process_video`` checks whether an
index already exists and returns immediately without re-processing if it does,
so running this multiple times is safe.

Why this is separate from the eval run
---------------------------------------
Indexing is expensive (frame extraction, ASR, captioning, embedding — all
real API calls), takes minutes per video, and should only happen once.
Conflating it with eval would make every retrieval score depend on whether
the processing pipeline happened to work that day, not whether retrieval
logic improved. See eval/README.md §"Why isn't the video indexed
automatically" for the full rationale.
"""
from __future__ import annotations

import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Videos to index.  These must match the ``video_path`` values used in the
# LangSmith dataset (see seed_datasets.py → VIDEO_PATH).
# The paths are relative to video_mcp_server's SHARED_MEDIA_DIR, which is
# what process_video() expects.
# ---------------------------------------------------------------------------
VIDEOS_TO_INDEX: list[str] = [
    "shared_media/example_video.mp4",
]


def _check_video_file_exists(video_path: str) -> bool:
    """Return True if the actual video file can be found on disk.

    process_video() will fail with a confusing error if the file is missing,
    so we surface a clear message here first.
    """
    from video_mcp_server.config import get_settings

    settings = get_settings()
    # video_path values in the registry are relative to the project root,
    # not to SHARED_MEDIA_DIR, so check both interpretations.
    candidates = [
        Path(video_path),                               # absolute or cwd-relative
        settings.SHARED_MEDIA_DIR.parent / video_path, # project-root-relative
    ]
    return any(p.exists() for p in candidates)


def index_videos(videos: list[str]) -> None:
    import pixeltable as pxt
    from video_mcp_server.tools import process_video

    total = len(videos)
    succeeded: list[str] = []
    failed: list[tuple[str, str]] = []

    try:
        for i, video_path in enumerate(videos, 1):
            print(f"\n[{i}/{total}] Processing: {video_path!r}")

            if not _check_video_file_exists(video_path):
                msg = (
                    f"Video file not found on disk: {video_path!r}\n"
                    f"  Place the file at that path (relative to the project root) "
                    f"and re-run this script."
                )
                print(f"  SKIP — {msg}")
                failed.append((video_path, msg))
                continue

            try:
                ok = process_video(video_path)
                if ok:
                    print(f"  OK — indexed successfully (or was already indexed).")
                    succeeded.append(video_path)
                else:
                    msg = "process_video() returned False — check logs above."
                    print(f"  FAIL — {msg}")
                    failed.append((video_path, msg))
            except Exception as exc:
                msg = str(exc)
                print(f"  FAIL — {exc}")
                failed.append((video_path, msg))
    finally:
        # Always shut down Pixeltable's embedded postgres cleanly so the
        # process doesn't stay alive holding the log file open.  Without
        # this, any Python exit (including on error) leaves postgres running,
        # which causes "sharing violation" timeouts on the next start.
        try:
            pxt.shutdown()
        except Exception:
            pass

    # Summary
    print("\n" + "=" * 60)
    print(f"Done.  {len(succeeded)}/{total} video(s) indexed successfully.")
    if failed:
        print(f"\nFailed ({len(failed)}):")
        for path, reason in failed:
            print(f"  • {path!r}: {reason}")
        sys.exit(1)


if __name__ == "__main__":
    # Allow overriding the video list from the CLI:
    #   python index_test_videos.py shared_media/my_other_video.mp4 ...
    videos = sys.argv[1:] if len(sys.argv) > 1 else VIDEOS_TO_INDEX
    index_videos(videos)
