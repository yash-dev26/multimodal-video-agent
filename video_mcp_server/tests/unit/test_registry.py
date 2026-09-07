"""
U4: regression test for the P1 bug where registry.get_table(None) (no
active video) raised a raw, confusing TypeError from `**None` deep inside
CachedTable.from_metadata, instead of a clear, catchable ValueError.
Pure dict/logic -- no Pixeltable needed.
"""

import pytest

from video_mcp_server.video.ingestion import registry


def test_get_table_with_no_video_raises_clear_value_error():
    with pytest.raises(ValueError, match="No video specified"):
        registry.get_table(None)

    with pytest.raises(ValueError, match="No video specified"):
        registry.get_table("")


def test_get_table_with_unknown_video_raises_clear_value_error(monkeypatch):
    monkeypatch.setattr(registry, "get_registry", lambda: {})

    with pytest.raises(ValueError, match="not found in registry"):
        registry.get_table("shared_media/never_indexed.mp4")
