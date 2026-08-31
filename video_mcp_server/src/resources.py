from typing import Dict
from video_mcp_server.src.video.ingestion.models import CachedTable, CachedTableMetadata
from video_mcp_server.src.video.ingestion.registry import get_registry


def list_tables() -> Dict[str, str]:
    """List all video indexes currently available.

    Returns:
        A string listing the current video indexes.
    """
    keys = list(get_registry().keys())
    if not keys:
        return None
    
    response = {
        "message": "Current processed videos",
        "indexes": keys,
    }
    return response


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
    table_metadata = registry[table_name]
    table_info = CachedTableMetadata(**table_metadata)
    table = CachedTable.from_metadata(table_info)
    response = table.describe()
    return response