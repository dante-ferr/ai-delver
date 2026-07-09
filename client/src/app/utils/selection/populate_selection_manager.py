from typing import Callable, Sequence, Any
from .selection_element_group import SelectionElementGroup
from .selection_manager import SelectionManager
import customtkinter as ctk


def populate_selection_manager(
    selection_manager: SelectionManager,
    frames: Sequence[ctk.CTkFrame],
    default_frame: ctk.CTkFrame,
    on_select: Callable[[Any], None],
):
    """Factory for creating configured SelectionManager instances.

    Args:
        selection_manager: The SelectionManager instance to configure.
        frames: A list of frames to add to the SelectionManager.
        default_frame: The default frame.
        on_select: A function that takes the selected frame and does something with it.
    """
    default_group = None

    for frame in frames:

        def _on_select(frame=frame):
            on_select(frame)

        group = SelectionElementGroup(_on_select, frame)
        selection_manager.add_selection_element_group(group)

        if frame == default_frame:
            default_group = group

    if not default_group:
        raise ValueError(f"Default frame '{default_frame}' not found in frames")

    selection_manager.selected_element_group = default_group
