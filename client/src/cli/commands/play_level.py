"""Interactive Pyglet playtest for a handcrafted or generated level."""

from __future__ import annotations

import json
import sys

import pyglet

from level import LevelLoader, LevelResolveError, resolve_level_dir


def print_json(event: str, **kwargs):
    print(json.dumps({"event": event, **kwargs}), flush=True)


def run_play_level(args):
    """Launch an interactive Pyglet window (Left/Right + Space) for a level."""
    level_ref = str(getattr(args, "level", "") or "").strip()
    if not level_ref:
        print_json("error", message="--level is required.")
        sys.exit(1)

    try:
        level_dir = resolve_level_dir(level_ref)
    except LevelResolveError as exc:
        print_json("error", message=str(exc))
        sys.exit(1)

    try:
        level = LevelLoader().load_level(dir_path=level_dir)
    except Exception as exc:
        print_json("error", message=f"Error loading level '{level_ref}': {exc}")
        sys.exit(1)

    if level is None:
        print_json("error", message=f"Failed to load level '{level_ref}'.")
        sys.exit(1)

    # Import after level load so missing display deps fail with a clear message.
    from app_manager import app_manager
    from runtime_view.game import Game

    print_json(
        "play_level",
        name=level.name,
        path=str(level_dir),
        message="Controls: Left/Right arrows to run, Space to jump. Close the window to exit.",
    )

    game = Game(level)
    # Register so ViewableRuntime._on_window_close → stop_viewable_runtimes works.
    app_manager._game = game

    def _cli_on_close():
        app_manager.stop_viewable_runtimes()
        pyglet.app.exit()
        return pyglet.event.EVENT_HANDLED

    if game._window is not None:
        game.window.push_handlers(on_close=_cli_on_close)

    game.run()
    pyglet.app.run()
