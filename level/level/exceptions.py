class LevelError(Exception):
    """Base exception for level-related errors."""
    pass


class LevelLoadError(LevelError):
    """Raised when a level file fails to load or parse."""

    def __init__(self, file_path: str, message: str, original_exception: Exception = None):
        super().__init__(f"Failed to load level from '{file_path}': {message}")
        self.file_path = file_path
        self.original_exception = original_exception


class LevelValidationError(LevelError):
    """Raised when a level structure has validation issues."""

    def __init__(self, level_name: str, issues: list[str]):
        super().__init__(
            f"Level '{level_name}' failed validation:\n"
            + "\n".join(f" - {issue}" for issue in issues)
        )
        self.level_name = level_name
        self.issues = issues
