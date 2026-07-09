from level.config import PROJECT_ROOT
from pathlib import Path


def from_asset_relative_path(relative_path: str) -> Path:
    """Converts a project-relative path (e.g., /assets/...) back to an absolute path."""
    if relative_path.startswith("/"):
        # lstrip('/') to handle the leading slash correctly with path joining
        return PROJECT_ROOT / relative_path.lstrip("/")
    # If it's not a project-relative path, assume it's a standard path
    return Path(relative_path)
