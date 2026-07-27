"""Reset / recreate the live ``__session__`` agent workspace."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from .config import AGENT_SAVE_FOLDER_PATH, SESSION_STORAGE_KEY


def reset_session_workspace(*, from_name: str | None = None) -> dict:
    """Wipe ``data/agents/__session__`` and optionally re-seed from a named agent.

    Returns a summary dict suitable for CLI JSON events.
    """
    if not AGENT_SAVE_FOLDER_PATH:
        raise RuntimeError("Agent save folder path is not configured.")

    agents_root = Path(AGENT_SAVE_FOLDER_PATH)
    session_dir = agents_root / SESSION_STORAGE_KEY
    source_name = from_name.strip() if from_name and from_name.strip() else None

    if source_name == SESSION_STORAGE_KEY:
        raise ValueError(f"Cannot re-seed the session from '{SESSION_STORAGE_KEY}'.")

    if session_dir.exists():
        shutil.rmtree(session_dir)
    session_dir.mkdir(parents=True, exist_ok=True)

    if source_name:
        source_dir = agents_root / source_name
        if not source_dir.is_dir():
            # Missing bound agent — fall back to a blank session instead of failing.
            source_name = None
        else:
            # Replace empty session with a full copy of the bound agent.
            shutil.rmtree(session_dir)
            shutil.copytree(source_dir, session_dir)

            meta_path = session_dir / "agent.json"
            data: dict = {}
            if meta_path.is_file():
                try:
                    with open(meta_path, "r") as file:
                        loaded = json.load(file)
                    if isinstance(loaded, dict):
                        data = loaded
                except (OSError, json.JSONDecodeError):
                    data = {}
            display_name = str(data.get("name") or source_name).strip() or source_name
            data["name"] = display_name
            data["bound_name"] = source_name
            data["autosave"] = False
            data.setdefault("early_stop", False)
            data.setdefault("live", True)
            with open(meta_path, "w") as file:
                json.dump(data, file, indent=2, sort_keys=True)

            return {
                "name": display_name,
                "bound_name": source_name,
                "reseeded_from": source_name,
                "path": str(session_dir),
            }

    meta = {
        "name": "Brave Delver",
        "bound_name": None,
        "autosave": False,
        "early_stop": False,
        "live": True,
    }
    with open(session_dir / "agent.json", "w") as file:
        json.dump(meta, file, indent=2, sort_keys=True)

    return {
        "name": meta["name"],
        "bound_name": None,
        "reseeded_from": None,
        "path": str(session_dir),
    }
