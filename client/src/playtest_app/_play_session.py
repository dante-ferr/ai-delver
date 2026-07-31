"""In-process Pyglet play session driven by a CustomTkinter host tick."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pyglet

from level import Level


class PlaySession:
    """Owns a ``Game`` instance and a Tk ``after`` tick that drives pyglet."""

    def __init__(
        self,
        host: Any,
        *,
        on_stopped: Callable[[], None] | None = None,
    ):
        self._host = host
        self._on_stopped = on_stopped
        self._game = None
        self._tick_after_id: str | None = None
        self._active = False
        self._stopping = False

    @property
    def active(self) -> bool:
        return self._active and self._game is not None

    def start(self, level: Level) -> None:
        if self.active or self._stopping:
            raise RuntimeError("A play session is already running.")

        from app_manager import app_manager
        from runtime_view.game import Game

        # Stop any leftover runtime before opening a new window.
        if app_manager._game is not None or app_manager._replay is not None:
            app_manager.stop_viewable_runtimes()

        game = Game(level)
        app_manager._game = game
        self._game = game
        self._active = True

        def _on_close():
            self.stop()
            return pyglet.event.EVENT_HANDLED

        if game._window is not None:
            # Most-recently-pushed handler runs first; swallow the default close path.
            game.window.push_handlers(on_close=_on_close)

        game.run()
        self._schedule_tick()

    def stop(self) -> None:
        if self._stopping or (not self._active and self._game is None):
            return

        self._stopping = True
        self._active = False
        self._cancel_tick()

        from app_manager import app_manager

        try:
            if app_manager._game is not None:
                app_manager.stop_game()
        finally:
            self._game = None
            self._stopping = False
            if self._on_stopped is not None:
                self._on_stopped()

    def _schedule_tick(self) -> None:
        self._cancel_tick()
        self._tick_after_id = self._host.after(16, self._tick)

    def _cancel_tick(self) -> None:
        if self._tick_after_id is not None:
            try:
                self._host.after_cancel(self._tick_after_id)
            except Exception:
                pass
            self._tick_after_id = None

    def _tick(self) -> None:
        self._tick_after_id = None
        if not self._active:
            return

        from app_manager import app_manager

        if app_manager._game is None:
            self._active = False
            self._game = None
            if self._on_stopped is not None:
                self._on_stopped()
            return

        try:
            pyglet.clock.tick(poll=True)
        except Exception:
            self.stop()
            return

        if self._active:
            self._schedule_tick()
