"""Standalone level browser / playtest secondary app."""

from __future__ import annotations

__all__ = ["PlaytestApp", "run_playtest_app"]


def __getattr__(name: str):
    if name in ("PlaytestApp", "run_playtest_app"):
        from .playtest_app import PlaytestApp, run_playtest_app

        return PlaytestApp if name == "PlaytestApp" else run_playtest_app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
