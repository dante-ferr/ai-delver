from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from .selection_element_group import SelectionElementGroup


def default_activate_callback(selection_element_group: "SelectionElementGroup"):
    selection_element_group.frame.configure(fg_color=("gray75", "gray25"))


def default_deactivate_callback(selection_element_group: "SelectionElementGroup"):
    selection_element_group.frame.configure(fg_color="transparent")


class SelectionManager:
    def __init__(
        self,
        initial_selection_element_group: "SelectionElementGroup | None" = None,
        activate_callback: Callable = default_activate_callback,
        deactivate_callback: Callable = default_deactivate_callback,
    ):
        self._selected_element_group = initial_selection_element_group

        self.selection_element_groups: list[SelectionElementGroup] = []

        self.activate_callback = activate_callback
        self.deactivate_callback = deactivate_callback

    def add_selection_element_group(
        self, selection_element_group: "SelectionElementGroup"
    ):
        selection_element_group.set_manager(self)
        selection_element_group.activate_callback = self.activate_callback
        selection_element_group.deactivate_callback = self.deactivate_callback
        self.selection_element_groups.append(selection_element_group)

    @property
    def selected_element_group(self):
        return self._selected_element_group

    @selected_element_group.setter
    def selected_element_group(self, selection_element_group: "SelectionElementGroup"):
        if (
            self._selected_element_group
            and self._selected_element_group != selection_element_group
        ):
            self._selected_element_group.deselect()
        self._selected_element_group = selection_element_group

        selection_element_group.select()
        selection_element_group.on_select()
