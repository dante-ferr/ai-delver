"""CLI entry for the standalone level playtest browser GUI."""

from __future__ import annotations


def run_playtest_gui(_args=None):
    """Launch the CustomTkinter level browser (minimap + play)."""
    from playtest_app import run_playtest_app

    run_playtest_app()
