"""Client-side checkpoint storage with level/date metadata."""

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
    return legacy


def list_checkpoints(agent: Agent | str) -> list[dict[str, Any]]:
    """Return all checkpoints (manifest + unmigrated legacy), newest first."""
    manifest = _read_manifest(agent)
    entries = [
        entry
        for entry in manifest.get("checkpoints", [])
        if isinstance(entry, dict) and entry.get("file")
    ]

    directory = checkpoints_dir(agent)
    existing = []
    for entry in entries:
        file_path = directory / entry["file"]
        if file_path.is_file():
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
) -> dict[str, Any]:
    """Persist weights and append a manifest entry. Returns the new entry."""
    directory = checkpoints_dir(agent)
    directory.mkdir(parents=True, exist_ok=True)

    entry_id = str(uuid.uuid4())
    filename = f"{entry_id}.zip"
    file_path = directory / filename
    with open(file_path, "wb") as f:
        f.write(weights_bytes)

    entry = {
        "id": entry_id,
        "file": filename,
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
            path = directory / entry["file"]
            return path if path.is_file() else None

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
                path = directory / entry["file"]
                if path.is_file():
                    return path
        legacy = directory / f"cycle_{key}.zip"
        if legacy.is_file():
            return legacy

    for entry in entries:
        if entry.get("file") == key or entry.get("file") == f"{key}.zip":
            path = directory / entry["file"]
            if path.is_file():
                return path

    return None


def restore_checkpoint(agent: Agent | str, checkpoint_id: str) -> Path:
    """Copy a checkpoint's weights onto the agent's model_weights.zip."""
    agent_obj = agent if isinstance(agent, Agent) else Agent(agent)
    if not agent_obj.weights_path:
        raise ValueError("Agent has no weights path configured.")

    source = resolve_checkpoint(agent_obj, checkpoint_id)
    if source is None or not source.is_file():
        raise FileNotFoundError(f"Checkpoint '{checkpoint_id}' not found.")

    agent_obj.weights_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, agent_obj.weights_path)
    return agent_obj.weights_path


def save_pre_level_checkpoints(agent: Agent | str, levels: list[str]) -> list[dict[str, Any]]:
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
        )
        saved.append(entry)
    return saved
