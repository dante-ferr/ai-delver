"""CLI: regenerate DragonBones representations (and Delver GIFs)."""

from __future__ import annotations

import sys

from src.utils.dragonbones_assets import regen_all


def run_regen_dragonbones(_args) -> None:
    try:
        written = regen_all(verbose=True)
    except Exception as exc:
        print(f"error: failed to regenerate DragonBones assets: {exc}", file=sys.stderr)
        sys.exit(1)

    if not written:
        sys.exit(1)
    print(f"Regenerated {len(written)} asset(s).")
