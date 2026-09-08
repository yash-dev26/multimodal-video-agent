"""
U5: extract_video_clip's start/end validation guard is pure and raises
before ever touching ffmpeg or a real video file -- no fixture video
needed to exercise it.
"""

import pytest

from video_mcp_server.video.ingestion.tools import extract_video_clip


def test_extract_video_clip_rejects_non_positive_duration():
    with pytest.raises(ValueError, match="start_time must be less than end_time"):
        extract_video_clip(
            video_path="irrelevant.mp4", start_time=10.0, end_time=5.0, output_path="out.mp4"
        )

    with pytest.raises(ValueError, match="start_time must be less than end_time"):
        extract_video_clip(
            video_path="irrelevant.mp4", start_time=5.0, end_time=5.0, output_path="out.mp4"
        )
