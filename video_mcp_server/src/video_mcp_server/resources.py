import json

from video_mcp_server.video.ingestion.models import CachedTable
from video_mcp_server.video.ingestion.registry import get_registry


def list_tables() -> str:
    """List all video indexes currently available.

    Returns:
        A JSON string listing the current video indexes.
    """
    keys = list(get_registry().keys())
    if not keys:
        return json.dumps({"message": "No videos have been processed yet.", "indexes": []})

    return json.dumps({"message": "Current processed videos", "indexes": keys})


def table_info(table_name: str) -> str:
    """List information about a specific video index.

    Args:
        table_name: The name of the video index to list information for.

    Returns:
        A string with the information about the video index.
    """
    registry = get_registry()
    if table_name not in registry:
        return f"Video index '{table_name}' does not exist."
    # Registry entries are either a JSON string (just-registered, in-memory)
    # or a CachedTableMetadata (loaded from disk) — never a plain dict.
    table = CachedTable.from_metadata(
        json.loads(registry[table_name])
        if isinstance(registry[table_name], str)
        else registry[table_name]
    )
    return table.describe()
