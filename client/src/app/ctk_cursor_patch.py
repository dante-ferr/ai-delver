"""Patch CustomTkinter so disabled / blocked widgets show a forbidden cursor.

CustomTkinter only sets hover/disabled cursors on Windows and macOS, so on Linux
disabled buttons often keep ``hand2``. This patch applies a platform-appropriate
forbidden cursor whenever interactive widgets enter a disabled state.
"""

from __future__ import annotations

import sys
import tkinter

import customtkinter as ctk

_APPLIED = False


def _forbidden_cursor() -> str:
    if sys.platform.startswith("win"):
        return "no"
    # X11 / Linux built-in "X" cursor is the classic forbidden pointer.
    # macOS Tk has no dedicated not-allowed cursor; X_cursor is still readable.
    return "X_cursor"


def _hand_cursor() -> str:
    if sys.platform == "darwin":
        return "pointinghand"
    return "hand2"


def _is_disabled(state) -> bool:
    return state in (tkinter.DISABLED, "disabled")


def _apply_cursor(widget, cursor: str) -> None:
    try:
        widget.configure(cursor=cursor)
    except Exception:
        pass


def _apply_canvas_label_cursor(widget, cursor: str) -> None:
    canvas = getattr(widget, "_canvas", None)
    if canvas is not None:
        try:
            canvas.configure(cursor=cursor)
        except Exception:
            pass
    label = getattr(widget, "_text_label", None)
    if label is not None:
        try:
            label.configure(cursor=cursor)
        except Exception:
            pass


def _patch_set_cursor_self(cls) -> None:
    """Replace ``_set_cursor`` that calls ``self.configure(cursor=...)``."""

    forbidden = _forbidden_cursor()
    hand = _hand_cursor()

    def _set_cursor(self):
        if not getattr(self, "_cursor_manipulation_enabled", True):
            return
        state = getattr(self, "_state", tkinter.NORMAL)
        if _is_disabled(state):
            _apply_cursor(self, forbidden)
        elif state in (tkinter.NORMAL, "normal"):
            _apply_cursor(self, hand)

    cls._set_cursor = _set_cursor


def _patch_set_cursor_canvas_label(cls) -> None:
    """Replace ``_set_cursor`` that targets canvas + optional text label."""

    forbidden = _forbidden_cursor()
    hand = _hand_cursor()

    def _set_cursor(self):
        if not getattr(self, "_cursor_manipulation_enabled", True):
            return
        state = getattr(self, "_state", tkinter.NORMAL)
        if _is_disabled(state):
            _apply_canvas_label_cursor(self, forbidden)
        elif state in (tkinter.NORMAL, "normal"):
            _apply_canvas_label_cursor(self, hand)

    cls._set_cursor = _set_cursor


def _sync_state_cursor(widget, *, use_canvas_label: bool = False) -> None:
    if not getattr(widget, "_cursor_manipulation_enabled", True):
        return
    state = getattr(widget, "_state", tkinter.NORMAL)
    cursor = _forbidden_cursor() if _is_disabled(state) else _hand_cursor()
    if use_canvas_label:
        _apply_canvas_label_cursor(widget, cursor)
    else:
        _apply_cursor(widget, cursor)


def _patch_configure_state_cursor(cls, *, use_canvas_label: bool = False) -> None:
    """Ensure state changes (and init) update the cursor for widgets without ``_set_cursor``."""

    original_configure = cls.configure
    original_init = cls.__init__

    def configure(self, require_redraw=False, **kwargs):
        state = kwargs.get("state", None)
        result = original_configure(self, require_redraw=require_redraw, **kwargs)
        if state is not None:
            _sync_state_cursor(self, use_canvas_label=use_canvas_label)
        return result

    def __init__(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        _sync_state_cursor(self, use_canvas_label=use_canvas_label)

    cls.configure = configure
    cls.__init__ = __init__


def apply_ctk_cursor_patch() -> None:
    global _APPLIED
    if _APPLIED:
        return
    _APPLIED = True

    _patch_set_cursor_self(ctk.CTkButton)
    _patch_set_cursor_self(ctk.CTkSlider)
    _patch_set_cursor_canvas_label(ctk.CTkCheckBox)
    _patch_set_cursor_canvas_label(ctk.CTkSwitch)
    _patch_set_cursor_canvas_label(ctk.CTkRadioButton)

    # These set a hand cursor at init but never sync it on disable.
    _patch_configure_state_cursor(ctk.CTkOptionMenu)
    _patch_configure_state_cursor(ctk.CTkComboBox, use_canvas_label=True)
    _patch_configure_state_cursor(ctk.CTkEntry)
