"""Level package configuration (TOML + UPPER_SNAKE attribute access)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Union

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib  # type: ignore


class Config:
    """Hold and provide access to configuration settings from a TOML file.

    File-backed instances re-read the TOML when the file's mtime changes, so
    edits apply without restarting a long-lived process (e.g. playtest GUI).
    """

    def __init__(
        self,
        config_source: Union[str, Path, Dict[str, Any], None] = None,
    ):
        if config_source is None:
            config_source = Path(__file__).resolve().parent / "config.toml"

        if isinstance(config_source, (str, Path)):
            self._config_path: Path | None = Path(config_source)
            self._mtime_ns: int | None = None
            self._data = self._load_config()
        elif isinstance(config_source, dict):
            self._config_path = None
            self._mtime_ns = None
            self._data = config_source
        else:
            raise TypeError("config_source must be a path, dictionary, or None.")

        if self._config_path is not None:
            object.__setattr__(self, "PROJECT_ROOT", self.get_project_root())
            object.__setattr__(self, "ASSETS_PATH", self.PROJECT_ROOT / "assets")

    def _load_config(self) -> dict:
        if self._config_path is None:
            return {}
        with open(self._config_path, "rb") as f:
            data = tomllib.load(f)
        try:
            self._mtime_ns = self._config_path.stat().st_mtime_ns
        except OSError:
            self._mtime_ns = None
        return data

    def reload(self) -> None:
        """Force re-read from disk (no-op for nested dict configs)."""
        if self._config_path is None:
            return
        self._data = self._load_config()
        object.__setattr__(self, "PROJECT_ROOT", self.get_project_root())
        object.__setattr__(self, "ASSETS_PATH", self.PROJECT_ROOT / "assets")

    def _refresh_if_stale(self) -> None:
        if self._config_path is None:
            return
        try:
            mtime = self._config_path.stat().st_mtime_ns
        except OSError:
            return
        if self._mtime_ns is None or mtime != self._mtime_ns:
            self._data = self._load_config()

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        self._refresh_if_stale()
        # UPPER_SNAKE_CASE attribute access → toml snake_case lookup.
        key = name.lower()
        if key in self._data:
            value = self._data[key]
            if isinstance(value, dict):
                return Config(value)
            return value
        raise AttributeError(
            f"Configuration '{self._config_path or 'nested config'}' has no setting '{key}'"
        )

    def get(self, key: str, default: Any = None) -> Any:
        """Return a raw snake_case key, or ``default`` if missing."""
        self._refresh_if_stale()
        return self._data.get(key, default)

    def as_dict(self) -> dict[str, Any]:
        self._refresh_if_stale()
        return dict(self._data)

    def get_project_root(self) -> Path:
        """Project root whether running from source or a frozen executable."""
        if getattr(sys, "frozen", False):
            application_path = Path(sys.executable)
            return application_path.parent
        # level/level/config.py → level/ → project root
        return Path(__file__).resolve().parent.parent.parent


# Global instances (mutate in place on reload — keep the same object identity).
config = Config()
procedural_config = Config(
    Path(__file__).resolve().parent / "procedural_platforming.toml"
)

_MODULE_ALIASES = {
    "PROJECT_ROOT": lambda: config.PROJECT_ROOT,
    "ASSETS_PATH": lambda: config.ASSETS_PATH,
    "TILEMAP_LAYER_NAMES": lambda: config.TILEMAP_LAYER_NAMES,
    "LAYER_ORDER": lambda: config.LAYER_ORDER,
    "START_MAP_WIDTH": lambda: config.START_MAP_WIDTH,
    "START_MAP_HEIGHT": lambda: config.START_MAP_HEIGHT,
    "START_DELVER_POSITION": lambda: tuple(config.START_DELVER_POSITION),
    "START_GOAL_POSITION": lambda: tuple(config.START_GOAL_POSITION),
    "TILE_WIDTH": lambda: config.TILE_WIDTH,
    "TILE_HEIGHT": lambda: config.TILE_HEIGHT,
    "MIN_GRID_SIZE": lambda: tuple(config.MIN_GRID_SIZE),
    "MAX_GRID_SIZE": lambda: tuple(config.MAX_GRID_SIZE),
    "LEVEL_SAVE_FOLDER_PATH": lambda: config.LEVEL_SAVE_FOLDER_PATH,
    "HANDCRAFTED_LEVEL_SAVE_FOLDER_PATH": lambda: (
        config.HANDCRAFTED_LEVEL_SAVE_FOLDER_PATH
    ),
    "GENERATED_LEVEL_SAVE_FOLDER_PATH": lambda: (
        config.GENERATED_LEVEL_SAVE_FOLDER_PATH
    ),
}


def __getattr__(name: str) -> Any:
    """Lazy module aliases so ``level.config.TILE_WIDTH`` tracks reloads."""
    factory = _MODULE_ALIASES.get(name)
    if factory is not None:
        return factory()
    raise AttributeError(f"module 'level.config' has no attribute {name!r}")


def _sync_module_aliases() -> None:
    """Publish aliases into the module dict for ``import *`` / static imports."""
    module = sys.modules[__name__]
    for name, factory in _MODULE_ALIASES.items():
        setattr(module, name, factory())


def reload_configs() -> None:
    """Re-read ``config.toml`` and ``procedural_platforming.toml`` from disk."""
    config.reload()
    procedural_config.reload()
    _sync_module_aliases()


_sync_module_aliases()


def get_project_root() -> Path:
    """Public alias matching the previous helper."""
    return config.get_project_root()
