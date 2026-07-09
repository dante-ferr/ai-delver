import sys
import json
from pathlib import Path
from typing import Any, Dict, Union


class Config:
    """A class to hold and provide access to configuration settings from a JSON file."""

    def __init__(self, config_source: Union[str, Dict[str, Any]] = "src/config.json"):
        if isinstance(config_source, str):
            self._config_path: Path | None = Path(config_source)
            self._data = self._load_config()
        elif isinstance(config_source, dict):
            self._config_path = None  # No file path for nested configs
            self._data = config_source
        else:
            raise TypeError("config_source must be a string path or a dictionary.")

        # These are top-level properties, only set for the main config instance
        if self._config_path is not None:
            self.PROJECT_ROOT = self.get_project_root()
            self.ASSETS_PATH = self.PROJECT_ROOT / "assets"

    def _load_config(self) -> dict:
        if self._config_path is None:
            return {}
        with open(self._config_path, "r") as f:
            return json.load(f)

    def __getattr__(self, name: str) -> Any:
        # Converts Python's UPPER_SNAKE_CASE attribute access to json's snake_case for lookup.
        key = name.lower()
        if key in self._data:
            value = self._data[key]
            if isinstance(value, dict):
                # If the value is a dictionary, return a new Config instance for it
                return Config(value)
            return value
        raise AttributeError(
            f"Configuration '{self._config_path or 'nested config'}' has no setting '{key}'"
        )

    def get_project_root(self) -> Path:
        """
        Determines the project's root directory, whether running from source
        or as a frozen executable (e.g., from PyInstaller).
        """
        if getattr(sys, "frozen", False):
            # If frozen, the root is the directory containing the executable.
            application_path = Path(sys.executable)
            return application_path.parent
        else:
            # If not frozen, we are running from source. The project root is derived
            # from this file's location.
            return Path(__file__).resolve().parent.parent.parent


# A single, global instance for easy access throughout the application.
config = Config()
