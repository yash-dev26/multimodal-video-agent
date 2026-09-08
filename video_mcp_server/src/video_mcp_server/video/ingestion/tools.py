import base64
import subprocess
from io import BytesIO
from pathlib import Path

import av
import loguru
from moviepy import VideoFileClip
from PIL import Image

logger = loguru.logger.bind(name="VideoTools")


def extract_video_clip(
    video_path: str, start_time: float, end_time: float, output_path: str = None
) -> str:
    """Extract a clip from ``video_path`` between ``start_time`` and
    ``end_time`` using ffmpeg directly (MoviePy's own trimming crashes on
    videos longer than a few minutes, so ffmpeg does the actual encoding).

    Returns:
        str: Path to the extracted clip file.
    """

    if start_time >= end_time:
        raise ValueError("start_time must be less than end_time")

    ## Anatomy of FFMPEG command
    # -i = input file
    # -ss/-to = start and end time of the clip, formatted as seconds or hh:mm:ss
    # -c (:v, :a) = sets the codec for the audio, and video channels
    # -preset = encoding speed/quality split
    # last argument is the output video path (if using libx264, it must end with .mp4)
    command = [
        "ffmpeg",
        "-ss",
        str(start_time),
        "-to",
        str(end_time),
        "-i",
        video_path,
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "23",
        "-c:a",
        "copy",
        "-y",
        output_path,
    ]

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    if process.returncode != 0:
        raise OSError(
            f"ffmpeg failed to extract clip (exit {process.returncode}): {stderr.decode('utf-8', errors='ignore')}"
        )
    logger.debug(f"FFmpeg output: {stdout.decode('utf-8', errors='ignore')}")

    # FIX (P2 - generated VideoFileClip isn't explicitly closed): callers
    # only ever need the output path (see tools.py), but the previous
    # implementation returned a live VideoFileClip, which holds an ffmpeg
    # reader process/file handle open until .close() is called. Nothing
    # downstream ever closed it, so the object (and its handle) leaked
    # until garbage collection got around to it — non-deterministic, and
    # a real risk of file-descriptor/subprocess exhaustion under load.
    # We open it only long enough to confirm/read the path, then close it
    # immediately and return a plain string.
    clip = VideoFileClip(output_path)
    try:
        return clip.filename
    finally:
        clip.close()


def encode_image(image: str | Image.Image) -> str:
    """Encode an image to base64 string.

    Args:
        image (Union[str, Image.Image]): Either a file path to an image or a PIL Image object

    Returns:
        str: Base64 encoded string representation of the image

    Raises:
        FileNotFoundError: If the image path does not exist
        IOError: If there are issues reading or processing the image
    """
    try:
        if isinstance(image, str):
            with open(image, "rb") as image_file:
                image_str = image_file.read()
        else:
            if not image.format:
                image_format = "JPEG"
            else:
                image_format = image.format

            buffered = BytesIO()
            image.save(buffered, format=image_format)
            image_str = buffered.getvalue()

        return base64.b64encode(image_str).decode("utf-8")

    except (OSError, FileNotFoundError) as e:
        raise OSError(f"Failed to process image: {str(e)}")


def decode_image(base64_string: str) -> Image.Image:
    """Decode a base64 string back into a PIL Image object.

    Args:
        base64_string (str): Base64 encoded string representation of an image

    Returns:
        Image.Image: PIL Image object

    Raises:
        ValueError: If the base64 string is invalid
        IOError: If there are issues processing the image data
    """
    try:
        image_bytes = base64.b64decode(base64_string)
        image_buffer = BytesIO(image_bytes)

        return Image.open(image_buffer)

    except (OSError, ValueError) as e:
        raise OSError(f"Failed to decode image: {str(e)}")


def _try_ffmpeg_pass(command: list, output_path: Path) -> str | None:
    """Run an ffmpeg command and return output_path as a str if PyAV can open the result, else None."""
    logger.info(f"Attempting: {' '.join(command)}")
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        logger.debug(f"FFmpeg stdout: {result.stdout}")
        logger.debug(f"FFmpeg stderr: {result.stderr}")
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg failed for {output_path}: {e.stderr}")
        return None

    try:
        with av.open(output_path) as _:
            logger.info(f"{output_path} successfully opened by PyAV.")
            return str(output_path)
    except Exception as e:
        logger.warning(f"{output_path} still not openable by PyAV: {e}")
        return None


def re_encode_video(video_path: str) -> str | None:
    """
    Re-encode a video file to ensure compatibility with PyAV.

    Tries a cheap `-c copy` remux first (fixes container-level issues like a
    bad moov atom without touching the actual streams). Only falls back to a
    full re-encode — slower, lossy — if the remux still isn't PyAV-openable.

    Returns the path to a PyAV-openable video, or None if it couldn't be
    opened or re-encoded.
    """
    if not Path(video_path).exists():
        logger.error(f"Error: Video file not found at {video_path}")
        return None

    try:
        with av.open(video_path) as _:
            logger.info(f"Video {video_path} successfully opened by PyAV.")
            return str(video_path)
    except Exception as e:
        logger.warning(f"PyAV couldn't open {video_path} directly, attempting remux/re-encode: {e}")

    o_dir, o_fname = Path(video_path).parent, Path(video_path).name
    remuxed_path = o_dir / f"remux_{o_fname}"
    reencoded_path = o_dir / f"re_{o_fname}"

    remux_command = ["ffmpeg", "-y", "-i", video_path, "-c", "copy", str(remuxed_path)]
    result = _try_ffmpeg_pass(remux_command, remuxed_path)
    if result:
        return result

    logger.info(f"Remux didn't fix {video_path}, falling back to a full re-encode.")
    reencode_command = [
        "ffmpeg",
        "-y",
        "-i",
        video_path,
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        str(reencoded_path),
    ]
    return _try_ffmpeg_pass(reencode_command, reencoded_path)
