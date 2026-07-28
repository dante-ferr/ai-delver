from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .run_grid import RunGrid


class RunGridData:
    def __init__(self, grid: "RunGrid"):
        self.grid = grid

    def apply_backfill(self, run_index, metadata):
        g = self.grid
        g._backfill_busy = False
        if isinstance(run_index, list):
            merged = list(g._run_index)
            while len(merged) < len(run_index):
                merged.append(None)
            for i, entry in enumerate(run_index):
                cur = merged[i] if i < len(merged) else None
                if isinstance(entry, dict) and (
                    not isinstance(cur, dict) or "victorious" not in cur
                ):
                    merged[i] = entry
            # Keep any newer complete slots beyond the backfill snapshot.
            g._run_index = merged
        if isinstance(metadata, dict):
            g._metadata = metadata
            archive = metadata.get("level_archive")
            if isinstance(archive, dict):
                g._level_archive = archive
            hashes = metadata.get("level_hashes")
            if isinstance(hashes, dict):
                g._level_hashes = hashes
        g.data.rebuild_visible()
        g.renderer.redraw()
        g.legend.rebuild_legend()

    def backfill_done(self):
        g = self.grid
        g._backfill_busy = False

    def ensure_visible_entries(self, indices: list[int]):
        g = self.grid
        """Synchronously fill any missing run-index slots needed for drawing."""
        if g._trajectory_dir is None or not indices:
            return
        missing = [
            i
            for i in indices
            if not (
                0 <= i < len(g._run_index)
                and isinstance(g._run_index[i], dict)
                and "victorious" in g._run_index[i]
                and "kind" in g._run_index[i]
            )
        ]
        if not missing:
            return
        try:
            from runtime.episode_trajectory import ensure_run_index

            metadata = g._metadata if isinstance(g._metadata, dict) else {}
            metadata["trajectory_count"] = max(
                int(metadata.get("trajectory_count", 0) or 0),
                len(g._run_index),
                max(missing) + 1,
            )
            metadata["run_index"] = g._run_index
            ensure_run_index(
                metadata,
                g._trajectory_dir,
                write_missing=False,
                only_indices=missing,
            )
            g._run_index = list(metadata.get("run_index", g._run_index))
            g._metadata = metadata
        except Exception:
            pass

    def entry(self, index: int) -> dict | None:
        g = self.grid
        if 0 <= index < len(g._run_index):
            entry = g._run_index[index]
            return entry if isinstance(entry, dict) else None
        return None

    def on_filters_changed(self):
        g = self.grid
        g._wins_only = bool(g.wins_var.get())
        g._hide_play = bool(g.hide_play_var.get())
        g.data.rebuild_visible()
        g.renderer.redraw()

    def passes_filters(self, index: int, entry: dict) -> bool:
        g = self.grid
        if g._wins_only and not entry.get("victorious"):
            return False
        if g._hide_play and entry.get("kind") == "play":
            return False
        if g._level_filters and entry.get("level_hash") not in g._level_filters:
            return False
        return True

    def rebuild_visible(self):
        g = self.grid
        visible: list[int] = []
        filters_active = (
            g._wins_only or g._hide_play or bool(g._level_filters)
        )
        for i, entry in enumerate(g._run_index):
            if not isinstance(entry, dict):
                # Unknown until backfilled — show only when no filters are active.
                if not filters_active:
                    visible.append(i)
                continue
            if g.data.passes_filters(i, entry):
                visible.append(i)
        g._visible_indices = visible
        g._scroll_row = max(0, min(g._scroll_row, g.renderer.total_rows() - 1))

    def schedule_background_backfill(self):
        g = self.grid
        if g._backfill_busy or g._trajectory_dir is None:
            return
        missing = [
            i
            for i, entry in enumerate(g._run_index)
            if not (isinstance(entry, dict) and "victorious" in entry and "kind" in entry)
        ]
        if not missing:
            return

        g._backfill_busy = True
        trajectory_dir = g._trajectory_dir
        metadata = dict(g._metadata) if isinstance(g._metadata, dict) else {}
        snapshot = list(g._run_index)

        def worker():
            on_disk = metadata
            filled: list = snapshot
            try:
                from runtime.episode_trajectory import ensure_run_index, RUN_INDEX_KEY
                import json

                working = {
                    "trajectory_count": int(metadata.get("trajectory_count", 0) or 0),
                    "trajectory_kinds": list(metadata.get("trajectory_kinds") or []),
                    RUN_INDEX_KEY: list(snapshot),
                }
                ensure_run_index(
                    working, trajectory_dir, write_missing=True, only_indices=None
                )
                filled = working.get(RUN_INDEX_KEY, [])

                meta_path = trajectory_dir / "metadata.json"
                try:
                    if meta_path.is_file():
                        with open(meta_path, "r") as f:
                            on_disk = json.load(f)
                    else:
                        on_disk = {}
                    if not isinstance(on_disk, dict):
                        on_disk = {}
                    existing = on_disk.get(RUN_INDEX_KEY)
                    if not isinstance(existing, list):
                        existing = []
                    merged = list(existing)
                    while len(merged) < len(filled):
                        merged.append(None)
                    for i, entry in enumerate(filled):
                        cur = merged[i] if i < len(merged) else None
                        if isinstance(entry, dict) and (
                            not isinstance(cur, dict) or "victorious" not in cur
                        ):
                            merged[i] = entry
                    on_disk[RUN_INDEX_KEY] = merged
                    with open(meta_path, "w") as f:
                        json.dump(on_disk, f, indent=4)
                    filled = merged
                except OSError:
                    pass
                g.after(
                    0,
                    lambda f=filled, m=on_disk: g.data.apply_backfill(f, m),
                )
            except Exception:
                g.after(0, g.data.backfill_done)

        import threading

        threading.Thread(target=worker, daemon=True).start()

    def refresh_from_disk(self):
        g = self.grid
        """Reload run_index from metadata; lazily backfill missing slots."""
        try:
            from loaders import agent_loader
            from runtime.episode_trajectory import read_run_index_sync

            agent = getattr(agent_loader, "agent", None)
            loader = getattr(agent, "trajectory_loader", None) if agent else None
            if loader is None:
                g._run_index = []
                g._level_archive = {}
                g._level_hashes = {}
                g._trajectory_dir = None
                g._metadata = {}
                g.data.rebuild_visible()
                g.renderer.redraw()
                g.legend.rebuild_legend()
                return

            trajectory_dir = Path(loader.trajectory_dir)
            metadata, run_index = read_run_index_sync(trajectory_dir, backfill_all=False)
            g._trajectory_dir = trajectory_dir
            g._metadata = metadata
            g._run_index = list(run_index)
            archive = metadata.get("level_archive")
            g._level_archive = archive if isinstance(archive, dict) else {}
            hashes = metadata.get("level_hashes")
            g._level_hashes = hashes if isinstance(hashes, dict) else {}
            g.data.schedule_background_backfill()
        except Exception:
            g._run_index = []
            g._level_archive = {}
            g._level_hashes = {}
            g._trajectory_dir = None
            g._metadata = {}

        g.data.rebuild_visible()
        g.renderer.redraw()
        g.legend.rebuild_legend()

    def train_name_for_hash(self, level_hash: str) -> str:
        g = self.grid
        if not level_hash:
            return "unknown"
        info = g._level_archive.get(level_hash)
        if isinstance(info, dict) and info.get("name_at_first_train"):
            return str(info["name_at_first_train"])
        for name, digest in g._level_hashes.items():
            if digest == level_hash:
                return str(name)
        return "unknown"

    def truncate_hash(self, digest: str) -> str:
        g = self.grid
        if not digest:
            return "—"
        n = g.legend_hash_chars
        if len(digest) <= n:
            return digest
        return digest[:n]
