import json
import os
from datetime import datetime
from pathlib import Path

from loguru import logger

from video_mcp_server.video.ingestion.constants import DEFAULT_CACHED_TABLES_REGISTRY_DIR
from video_mcp_server.video.ingestion.models import CachedTable, CachedTableMetadata

logger = logger.bind(name="TableRegistry")

VIDEO_INDEXES_REGISTRY: dict[str, CachedTableMetadata] = {}


def get_registry() -> dict[str, CachedTableMetadata]:
    """
    Get the global video index registry.

    Returns:
        Dict[str, CachedTableMetadata]: The video index registry.
    """
    global VIDEO_INDEXES_REGISTRY
    if not VIDEO_INDEXES_REGISTRY:
        try:
            registry_files = [
                f
                for f in os.listdir(DEFAULT_CACHED_TABLES_REGISTRY_DIR)
                if f.startswith("registry_") and f.endswith(".json")
            ]
            if registry_files:
                latest_file = max(registry_files)
                latest_registry = Path(DEFAULT_CACHED_TABLES_REGISTRY_DIR) / latest_file
                with open(str(latest_registry)) as f:
                    VIDEO_INDEXES_REGISTRY = json.load(f)
                    for key, value in VIDEO_INDEXES_REGISTRY.items():
                        if isinstance(value, str):
                            value = json.loads(value)
                        VIDEO_INDEXES_REGISTRY[key] = CachedTableMetadata(**value)
                logger.info(f"Loading registry from {latest_registry}")
        except FileNotFoundError:
            logger.warning("Registry file not found. Returning empty registry.")
    else:
        logger.info("Using existing video index registry.")
    return VIDEO_INDEXES_REGISTRY


def add_index_to_registry(
    video_name: str,
    video_cache: str,
    frames_view_name: str,
    audio_view_name: str,
):
    """
    Register a video index in the global registry.

    Args:
        video_name (str): The name of the video.
        video_cache (str): The cache path for the video.
        frames_view_name (str): The name of the frames view.
        audio_view_name (str): The name of the audio chunks view.
    """
    global VIDEO_INDEXES_REGISTRY
    cached_table_meta = CachedTableMetadata(
        video_name=video_name,
        video_cache=video_cache,
        video_table=f"{video_cache}.table",
        frames_view=frames_view_name,
        audio_chunks_view=audio_view_name,
    ).model_dump_json()
    VIDEO_INDEXES_REGISTRY[video_name] = cached_table_meta

    dt = datetime.now()
    dtstr = dt.strftime("%Y-%m-%d%H:%M:%S")
    records_dir = Path(DEFAULT_CACHED_TABLES_REGISTRY_DIR)
    records_dir.mkdir(parents=True, exist_ok=True)
    with open(records_dir / f"registry_{dtstr}.json", "w") as f:
        for k, v in VIDEO_INDEXES_REGISTRY.items():
            if isinstance(v, CachedTableMetadata):
                v = v.model_dump_json()
            VIDEO_INDEXES_REGISTRY[k] = v
        json.dump(VIDEO_INDEXES_REGISTRY, f, indent=4)

    logger.info(f"Video index '{video_name}' registered in the global registry.")


def remove_index_from_registry(video_name: str) -> bool:
    """
    Remove a video's index entry so a future process_video() call re-indexes
    it from scratch instead of reusing a (possibly stale) cached table.

    FIX (P1 - re-uploading the same filename doesn't force re-indexing /
    P2 - removing a video from the UI doesn't clean up backend data): both
    of those bugs ultimately need a way to make VideoProcessor "forget" a
    video. This is that primitive.

    Args:
        video_name (str): The video path/key used when it was registered.

    Returns:
        bool: True if an entry was found and removed, False otherwise.
    """
    registry = get_registry()
    if video_name not in registry:
        return False

    del registry[video_name]

    dt = datetime.now()
    dtstr = dt.strftime("%Y-%m-%d%H:%M:%S")
    records_dir = Path(DEFAULT_CACHED_TABLES_REGISTRY_DIR)
    records_dir.mkdir(parents=True, exist_ok=True)
    with open(records_dir / f"registry_{dtstr}.json", "w") as f:
        json.dump(
            {
                k: (v.model_dump_json() if isinstance(v, CachedTableMetadata) else v)
                for k, v in registry.items()
            },
            f,
            indent=4,
        )

    logger.info(f"Video index '{video_name}' removed from the global registry.")
    return True


def get_table(video_name: str) -> CachedTable:
    """
    Look up a video's cached table metadata and hydrate a CachedTable.

    FIX (P1 - image query with no active/processed video enters a failure
    path): previously, calling this with `video_name=None` (no active video
    selected) fell through to `CachedTable.from_metadata(None)`, which
    raised a raw, confusing `TypeError: argument after ** must be a
    mapping, not NoneType` instead of a clear, catchable error. This now
    validates both the "no video specified" and "video never processed"
    cases explicitly with a `ValueError` that carries an actionable message.

    Args:
        video_name (str): The name of the video index to look up.

    Returns:
        CachedTable: The hydrated table/view handles for this video.

    Raises:
        ValueError: If no video was specified, or it hasn't been indexed.
    """
    if not video_name:
        raise ValueError(
            "No video specified — a video must be uploaded and processed before searching."
        )

    registry = get_registry()
    logger.info(f"Registry: {registry}")
    metadata = registry.get(video_name)
    if metadata is None:
        raise ValueError(
            f"Video index '{video_name}' not found in registry — has it been processed yet?"
        )

    if isinstance(metadata, str):
        metadata = json.loads(metadata)
    logger.info(f"Metadata: {metadata}")
    return CachedTable.from_metadata(metadata)
