"""Helpers for discarding unsaved level work with a confirmation dialog.

Agent session data is always written to ``__session__``, so agent load/close
paths do not prompt. Levels still need an explicit Save.
"""

from __future__ import annotations

from typing import Callable


def _level_dirty() -> bool:
    try:
        from loaders import level_loader

        return bool(getattr(level_loader, "dirty", False))
    except Exception:
        return False


def has_unsaved_changes(*, kind: str | None = "level") -> bool:
    """Return whether unsaved level work exists.

    ``kind`` is accepted for call-site clarity; only level dirtiness is checked.
    """
    return _level_dirty()


def confirm_discard_unsaved(
    *,
    kind: str | None = "level",
    on_discard: Callable[[], None],
    on_cancel: Callable[[], None] | None = None,
) -> None:
    """If the level is dirty, ask before running ``on_discard``; otherwise run it."""
    from app.components.overlay.message_overlay import MessageOverlay

    if not has_unsaved_changes(kind=kind):
        on_discard()
        return

    def _cancel():
        if on_cancel:
            on_cancel()

    MessageOverlay(
        "The current level has unsaved changes. Discard them and continue?",
        subject="Warning",
        button_commands={
            "Discard": on_discard,
            "Cancel": _cancel,
        },
    )
