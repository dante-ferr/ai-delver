from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .summary_panel import TrajectorySummaryPanel


class LevelMetaLookup:
    """Level hash display and global save matching for the summary panel."""

    def __init__(self, panel: "TrajectorySummaryPanel"):
        self.panel = panel

    def truncate_hash(self, digest: str) -> str:
        if not digest:
            return "—"
        try:
            from src.config import config

            hash_chars = int(config.LEVEL_ARCHIVE.HASH_DISPLAY_CHARS)
        except Exception:
            hash_chars = 12
        if len(digest) <= hash_chars:
            return digest
        return digest[:hash_chars]

    def get_name_at_first_train(self, target_hash: str) -> str:
        if not target_hash:
            return "unknown"

        try:
            from loaders import agent_loader

            agent = getattr(agent_loader, "agent", None)
            if agent is None or getattr(agent, "trajectory_loader", None) is None:
                return "unknown"

            trajectory_dir = Path(agent.trajectory_loader.trajectory_dir)
            meta_paths = [
                trajectory_dir / "metadata.json",
                trajectory_dir.parent / "trajectories" / "metadata.json",
            ]

            metadata = None
            for meta_path in meta_paths:
                if meta_path.is_file():
                    try:
                        with open(meta_path, "r") as f:
                            metadata = json.load(f)
                        break
                    except Exception:
                        continue

            if not isinstance(metadata, dict):
                return "unknown"

            archive = metadata.get("level_archive")
            if isinstance(archive, dict):
                info = archive.get(target_hash)
                if isinstance(info, dict) and info.get("name_at_first_train"):
                    return str(info["name_at_first_train"])

            hashes = metadata.get("level_hashes")
            if isinstance(hashes, dict):
                for name, digest in hashes.items():
                    if digest == target_hash:
                        return str(name)
        except Exception:
            pass

        return "unknown"

    def find_matching_global_levels(self, target_hash: str) -> list[str]:
        if not target_hash:
            return []

        try:
            from level.config import LEVEL_SAVE_FOLDER_PATH

            root = Path(LEVEL_SAVE_FOLDER_PATH)
            if not root.is_dir():
                return []

            matches: list[str] = []
            for child in sorted(root.iterdir(), key=lambda p: p.name.lower()):
                if not child.is_dir():
                    continue
                level_json = child / "level.json"
                if not level_json.is_file():
                    continue
                digest = self.hash_for_path(level_json)
                if digest == target_hash:
                    matches.append(child.name)
            return matches
        except Exception:
            return []

    def hash_for_path(self, path: Path) -> str | None:
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return None

        key = str(path)
        cached = self.panel._hash_cache.get(key)
        if cached is not None and cached[0] == mtime:
            return cached[1]

        try:
            with open(path, "r") as f:
                level_data = json.load(f)
            from level import Level

            digest = Level.hash_json(level_data)
        except Exception:
            return None

        self.panel._hash_cache[key] = (mtime, digest)
        return digest
