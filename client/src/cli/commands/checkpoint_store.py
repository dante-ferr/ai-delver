"""Client-side checkpoint storage with level/date metadata and curriculum bundles."""

from __future__ import annotations

import json
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent.agent import Agent

MANIFEST_NAME = "manifest.json"
WEIGHTS_NAME = "model_weights.ot"
CURRICULUM_NAME = "curriculum.json"
KIND_PRE_LEVEL = "pre_level"
KIND_INTERVAL = "interval"
KIND_LEGACY = "legacy"

_CYCLE_ZIP_RE = re.compile(r"^cycle_(\d+)\.zip$", re.IGNORECASE)


def checkpoints_dir(agent: Agent | str) -> Path:
    agent_obj = agent if isinstance(agent, Agent) else Agent(agent)
    if not agent_obj.weights_path:
        raise ValueError("Agent has no weights path configured.")
    return agent_obj.weights_path.parent / "checkpoints"


def _manifest_path(agent: Agent | str) -> Path:
    return checkpoints_dir(agent) / MANIFEST_NAME


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _read_manifest(agent: Agent | str) -> dict[str, Any]:
    path = _manifest_path(agent)
    if not path.is_file():
        return {"checkpoints": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"checkpoints": []}
    if not isinstance(data, dict):
        return {"checkpoints": []}
    entries = data.get("checkpoints")
    if not isinstance(entries, list):
        data["checkpoints"] = []
    return data


def _write_manifest(agent: Agent | str, data: dict[str, Any]) -> None:
    directory = checkpoints_dir(agent)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / MANIFEST_NAME
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def _weights_path_for_entry(directory: Path, entry: dict[str, Any]) -> Path | None:
    """Resolve the weights file for a manifest entry (bundle dir or legacy file)."""
    bundle_dir = entry.get("dir")
    if bundle_dir:
        path = directory / str(bundle_dir) / WEIGHTS_NAME
        return path if path.is_file() else None

    filename = entry.get("file")
    if filename:
        path = directory / str(filename)
        if path.is_file():
            return path
        # Bundle recorded with dir name in file field (defensive)
        as_dir = directory / str(filename)
        nested = as_dir / WEIGHTS_NAME
        if nested.is_file():
            return nested
    return None


def _curriculum_path_for_entry(directory: Path, entry: dict[str, Any]) -> Path | None:
    bundle_dir = entry.get("dir")
    if bundle_dir:
        path = directory / str(bundle_dir) / CURRICULUM_NAME
        return path if path.is_file() else None
    filename = entry.get("file")
    if filename:
        nested = directory / str(filename) / CURRICULUM_NAME
        if nested.is_file():
            return nested
    return None


def _legacy_entries(agent: Agent | str) -> list[dict[str, Any]]:
    """Build synthetic entries for cycle_*.zip files not yet in the manifest."""
    directory = checkpoints_dir(agent)
    if not directory.is_dir():
        return []

    manifest = _read_manifest(agent)
    known_files = {
        entry.get("file")
        for entry in manifest.get("checkpoints", [])
        if isinstance(entry, dict) and entry.get("file")
    }
    known_dirs = {
        entry.get("dir")
        for entry in manifest.get("checkpoints", [])
        if isinstance(entry, dict) and entry.get("dir")
    }

    legacy: list[dict[str, Any]] = []
    for path in sorted(directory.glob("cycle_*.zip")):
        if path.name in known_files:
            continue
        match = _CYCLE_ZIP_RE.match(path.name)
        cycle = int(match.group(1)) if match else None
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        legacy.append(
            {
                "id": f"legacy-{path.stem}",
                "file": path.name,
                "level": "unknown",
                "created_at": mtime.replace(microsecond=0).isoformat(),
                "cycle": cycle,
                "kind": KIND_LEGACY,
            }
        )

    # Orphan uuid directories with weights but no manifest entry
    for path in sorted(directory.iterdir()):
        if not path.is_dir():
            continue
        if path.name in known_dirs:
            continue
        weights = path / WEIGHTS_NAME
        if not weights.is_file():
            continue
        mtime = datetime.fromtimestamp(weights.stat().st_mtime, tz=timezone.utc)
        legacy.append(
            {
                "id": f"legacy-{path.name}",
                "dir": path.name,
                "level": "unknown",
                "created_at": mtime.replace(microsecond=0).isoformat(),
                "cycle": None,
                "kind": KIND_LEGACY,
            }
        )
    return legacy


def list_checkpoints(agent: Agent | str) -> list[dict[str, Any]]:
    """Return all checkpoints (manifest + unmigrated legacy), newest first."""
    manifest = _read_manifest(agent)
    entries = [
        entry
        for entry in manifest.get("checkpoints", [])
        if isinstance(entry, dict) and (entry.get("file") or entry.get("dir"))
    ]

    directory = checkpoints_dir(agent)
    existing = []
    for entry in entries:
        if _weights_path_for_entry(directory, entry) is not None:
            existing.append(entry)

    existing.extend(_legacy_entries(agent))
    existing.sort(key=lambda e: e.get("created_at") or "", reverse=True)
    return existing


def save_checkpoint(
    agent: Agent | str,
    weights_bytes: bytes,
    *,
    level: str,
    cycle: int | None,
    kind: str,
    curriculum: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist weights (+ optional curriculum) as a bundle and append a manifest entry."""
    directory = checkpoints_dir(agent)
    directory.mkdir(parents=True, exist_ok=True)

    entry_id = str(uuid.uuid4())
    bundle_dir = directory / entry_id
    bundle_dir.mkdir(parents=True, exist_ok=True)

    weights_path = bundle_dir / WEIGHTS_NAME
    with open(weights_path, "wb") as f:
        f.write(weights_bytes)

    if curriculum is not None:
        curriculum_path = bundle_dir / CURRICULUM_NAME
        with open(curriculum_path, "w", encoding="utf-8") as f:
            json.dump(curriculum, f, indent=2)
            f.write("\n")

    entry = {
        "id": entry_id,
        "dir": entry_id,
        "level": level,
        "created_at": _utc_now_iso(),
        "cycle": cycle,
        "kind": kind,
    }

    data = _read_manifest(agent)
    data.setdefault("checkpoints", []).append(entry)
    _write_manifest(agent, data)
    return entry


def resolve_checkpoint(agent: Agent | str, id_or_legacy: str) -> Path | None:
    """Resolve a checkpoint id, cycle number, or filename to a weights path."""
    key = str(id_or_legacy).strip()
    if not key:
        return None

    directory = checkpoints_dir(agent)
    entries = list_checkpoints(agent)

    for entry in entries:
        if entry.get("id") == key:
            return _weights_path_for_entry(directory, entry)

    # Direct bundle directory
    bundle_weights = directory / key / WEIGHTS_NAME
    if bundle_weights.is_file():
        return bundle_weights

    if key.endswith(".zip"):
        path = directory / key
        if path.is_file():
            return path
    else:
        path = directory / f"{key}.zip"
        if path.is_file():
            return path

    if key.isdigit():
        cycle = int(key)
        for entry in entries:
            if entry.get("cycle") == cycle:
                resolved = _weights_path_for_entry(directory, entry)
                if resolved is not None:
                    return resolved
        legacy = directory / f"cycle_{key}.zip"
        if legacy.is_file():
            return legacy

    for entry in entries:
        if entry.get("file") == key or entry.get("file") == f"{key}.zip":
            return _weights_path_for_entry(directory, entry)
        if entry.get("dir") == key:
            return _weights_path_for_entry(directory, entry)

    return None


def _find_entry(agent: Agent | str, checkpoint_id: str) -> dict[str, Any] | None:
    key = str(checkpoint_id).strip()
    for entry in list_checkpoints(agent):
        if entry.get("id") == key or entry.get("dir") == key or entry.get("file") == key:
            return entry
        if key.isdigit() and entry.get("cycle") == int(key):
            return entry
    return None


def load_checkpoint_curriculum(agent: Agent | str, checkpoint_id: str) -> dict[str, Any] | None:
    """Load curriculum.json from a checkpoint bundle, if present."""
    entry = _find_entry(agent, checkpoint_id)
    if entry is None:
        # Try direct dir
        directory = checkpoints_dir(agent)
        path = directory / str(checkpoint_id).strip() / CURRICULUM_NAME
        if path.is_file():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data if isinstance(data, dict) else None
            except (OSError, json.JSONDecodeError):
                return None
        return None

    path = _curriculum_path_for_entry(checkpoints_dir(agent), entry)
    if path is None or not path.is_file():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _apply_curriculum_sync(agent_name: str, curriculum: dict[str, Any]) -> None:
    """Synchronously merge a curriculum snapshot into trajectories/metadata.json."""
    from runtime.episode_trajectory._get_trajectory_dir import get_trajectory_dir
    from .review_planner import apply_curriculum_snapshot

    metadata_path = get_trajectory_dir(agent_name) / "metadata.json"
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata: dict[str, Any] = {"trajectory_count": 0, "stats": {"amount": 0, "victories": 0}}
    if metadata_path.is_file():
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                metadata = loaded
        except (OSError, json.JSONDecodeError):
            pass
    apply_curriculum_snapshot(metadata, curriculum)
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=4)
        f.write("\n")


def restore_checkpoint(agent: Agent | str, checkpoint_id: str) -> Path:
    """Copy a checkpoint's weights onto model_weights.zip and restore curriculum if bundled."""
    agent_obj = agent if isinstance(agent, Agent) else Agent(agent)
    if not agent_obj.weights_path:
        raise ValueError("Agent has no weights path configured.")

    source = resolve_checkpoint(agent_obj, checkpoint_id)
    if source is None or not source.is_file():
        raise FileNotFoundError(f"Checkpoint '{checkpoint_id}' not found.")

    agent_obj.weights_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, agent_obj.weights_path)

    curriculum = load_checkpoint_curriculum(agent_obj, checkpoint_id)
    if curriculum is not None:
        _apply_curriculum_sync(agent_obj.name, curriculum)

    return agent_obj.weights_path


def save_pre_level_checkpoints(
    agent: Agent | str,
    levels: list[str],
    *,
    curriculum: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Snapshot current model_weights as a pre_level checkpoint for each level."""
    agent_obj = agent if isinstance(agent, Agent) else Agent(agent)
    if not agent_obj.weights_path or not agent_obj.weights_path.is_file():
        return []

    with open(agent_obj.weights_path, "rb") as f:
        weights_bytes = f.read()

    saved: list[dict[str, Any]] = []
    for level in levels:
        entry = save_checkpoint(
            agent_obj,
            weights_bytes,
            level=level,
            cycle=None,
            kind=KIND_PRE_LEVEL,
            curriculum=curriculum,
        )
        saved.append(entry)
    return saved
