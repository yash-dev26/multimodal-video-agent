import json
import threading
from uuid import uuid4

import pixeltable as pxt
from langsmith import traceable
from loguru import logger

import video_mcp_server.video.ingestion.registry as registry
from video_mcp_server.config import get_settings
from video_mcp_server.video.ingestion.tools import extract_video_clip
from video_mcp_server.video.ingestion.video_processor import VideoProcessor
from video_mcp_server.video.video_search_service import VideoSearchEngine

logger = logger.bind(name="MCPVideoTools")
settings = get_settings()
settings.SHARED_MEDIA_DIR.mkdir(parents=True, exist_ok=True)

# FIX (P1 - shared mutable VideoProcessor can race during concurrent
# processing): VideoProcessor stores all per-video ingestion state
# (self.pxt_cache, self.video_table, self.frames_view, ...) as instance
# attributes, set inside setup_table(). The previous code instantiated ONE
# VideoProcessor at module import time and reused it for every call, so two
# process_video() calls running concurrently could clobber each other's
# in-flight state and cross-contaminate indexes. We now create a fresh
# VideoProcessor per call (see process_video() below) instead of sharing
# this singleton.
#
# _ingestion_lock additionally serializes the write/setup phase across
# concurrent calls — Pixeltable directory/table creation is shared I/O
# against the same on-disk store, independent of the Python-level instance
# race above, so it's serialized as a belt-and-suspenders measure. Reads
# (VideoSearchEngine, used by the other tools below) are unaffected and
# remain fully concurrent since each already builds its own instance.
_ingestion_lock = threading.Lock()


@traceable(name="process_video", run_type="tool")
def process_video(video_path: str) -> bool:
    """Process a video file and prepare it for searching.

    Args:
        video_path (str): Path to the video file to process.

    Returns:
        bool: True if the video is already indexed and ready, or was
            successfully processed. False if processing failed.

    Raises:
        ValueError: If the video file cannot be found or processed.
    """
    processor = VideoProcessor()

    if processor._check_if_exists(video_path):
        logger.info(f"Video index for '{video_path}' already exists and is ready for use.")
        return True

    with _ingestion_lock:
        # Re-check inside the lock: another thread may have just finished
        # indexing this exact video while we were waiting for the lock.
        if processor._check_if_exists(video_path):
            return True
        processor.setup_table(video_name=video_path)
        return processor.add_video(video_path=video_path)


@traceable(name="remove_video", run_type="tool")
def remove_video(video_path: str) -> bool:
    """Drop a video's cached index so it will be fully re-processed next time.

    Used when: a video is deleted from the UI (so stale embeddings don't
    linger and keep answering queries), and when a re-uploaded file
    replaces an existing one under the same name (so the new content gets
    indexed instead of the old index being silently reused).

    Args:
        video_path (str): The path/key the video was registered under.

    Returns:
        bool: True if an index existed and was removed, False if the video
            wasn't indexed in the first place.
    """
    raw_metadata = registry.get_registry().get(video_path)
    removed = registry.remove_index_from_registry(video_path)

    if removed and raw_metadata:
        metadata = json.loads(raw_metadata) if isinstance(raw_metadata, str) else raw_metadata
        cache_dir = metadata.get("video_cache") if isinstance(metadata, dict) else None
        if cache_dir:
            try:
                pxt.drop_dir(cache_dir, force=True)
            except Exception as e:
                logger.warning(f"Could not drop pixeltable cache dir '{cache_dir}': {e}")

    return removed


@traceable(name="get_video_clip_from_user_query", run_type="tool")
def get_video_clip_from_user_query(video_path: str, user_query: str) -> str:
    """Get a video clip based on the user query using speech and caption similarity.

    Args:
        video_path (str): The path to the video file.
        user_query (str): The user query to search for.

    Returns:
        str: Path to the extracted video clip.
    """
    search_engine = VideoSearchEngine(video_path)

    speech_clips = search_engine.search_by_speech(
        user_query, settings.VIDEO_CLIP_SPEECH_SEARCH_TOP_K
    )
    caption_clips = search_engine.search_by_caption(
        user_query, settings.VIDEO_CLIP_CAPTION_SEARCH_TOP_K
    )

    if not speech_clips and not caption_clips:
        raise ValueError(f"No matching clip found in '{video_path}' for query: {user_query!r}")

    speech_sim = speech_clips[0]["similarity"] if speech_clips else 0
    caption_sim = caption_clips[0]["similarity"] if caption_clips else 0

    # Determine which clip to use based on the highest similarity score
    video_clip_info = speech_clips[0] if speech_sim > caption_sim else caption_clips[0]

    clip_path = extract_video_clip(
        video_path=video_path,
        start_time=video_clip_info["start_time"],
        end_time=video_clip_info["end_time"],
        output_path=str(settings.SHARED_MEDIA_DIR / f"{str(uuid4())}.mp4"),
    )

    return clip_path


@traceable(name="get_video_clip_from_image", run_type="tool")
def get_video_clip_from_image(video_path: str, user_image: str) -> str:
    """Get a video clip based on similarity to a provided image.

    Args:
        video_path (str): The path to the video file.
        user_image (str): The query image encoded in base64 format.

    Returns:
        str: Path to the extracted video clip.
    """
    search_engine = VideoSearchEngine(video_path)
    image_clips = search_engine.search_by_image(user_image, settings.VIDEO_CLIP_IMAGE_SEARCH_TOP_K)

    if not image_clips:
        raise ValueError(f"No matching clip found in '{video_path}' for the provided image.")

    clip_path = extract_video_clip(
        video_path=video_path,
        start_time=image_clips[0]["start_time"],
        end_time=image_clips[0]["end_time"],
        output_path=str(settings.SHARED_MEDIA_DIR / f"{str(uuid4())}.mp4"),
    )

    return clip_path


@traceable(name="ask_question_about_video", run_type="tool")
def ask_question_about_video(video_path: str, user_query: str) -> str:
    """Get relevant captions from the video based on the user's question.

    Args:
        video_path (str): The path to the video file.
        user_query (str): The question to search for relevant captions.

    Returns:
        str: Concatenated relevant captions from the video.
    """
    search_engine = VideoSearchEngine(video_path)
    caption_info = search_engine.get_caption_info(user_query, settings.QUESTION_ANSWER_TOP_K)

    answer = "\n".join(entry["caption"] for entry in caption_info)
    return answer
