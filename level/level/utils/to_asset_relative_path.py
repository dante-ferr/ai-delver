from level.config import PROJECT_ROOT
from pathlib import Path


def to_asset_relative_path(absolute_path: str | Path) -> str:
    """Converts an absolute path to a path relative to the project root, prefixed with a slash."""
    try:
        # Ensure we are working with an absolute path for correct relativity
        abs_path = Path(absolute_path).resolve()
        relative_path = abs_path.relative_to(PROJECT_ROOT)
        # Return path with forward slashes for consistency across OS
        return f"/{relative_path.as_posix()}"
    except ValueError:
        # Path is not within the project root, return as is.
        return str(absolute_path)
