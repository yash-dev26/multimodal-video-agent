import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict

from loguru import logger

from video_mcp_server.video.ingestion.constants import DEFAULT_CACHED_TABLES_REGISTRY_DIR
from video_mcp_server.video.ingestion.models import CachedTable, CachedTableMetadata

logger = logger.bind(name="TableRegistry")

VIDEO_INDEXES_REGISTRY: Dict[str, CachedTableMetadata] = {}


def get_registry() -> Dict[str, CachedTableMetadata]:
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
                with open(str(latest_registry), "r") as f:
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
        video_path (str): The path to the video file.
        video_name (str): The name of the video.
        video_cache (str): The cache path for the video.
        video_table_name (str): The name of the video table.
        frames_view_name (str): The name of the frames view.
        sentences_view_name (str): The name of the sentences view.
        semantics_index_name (str): The name of the semantics index.

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


def get_table(video_name: str) -> Dict[str, CachedTable]:
    """
    Get the global video index registry.

    Returns:
        Dict[str, CachedTable]: The video index registry.
    """
    registry = get_registry()
    logger.info(f"Registry: {registry}")
    metadata = registry.get(video_name)
    if isinstance(metadata, str):
        metadata = json.loads(metadata)
    logger.info(f"Metadata: {metadata}")
    return CachedTable.from_metadata(metadata)