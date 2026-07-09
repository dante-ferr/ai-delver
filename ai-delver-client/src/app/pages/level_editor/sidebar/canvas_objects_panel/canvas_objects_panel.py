from app.utils.selection import populate_selection_manager, SelectionManager
from ._canvas_object_container import CanvasObjectContainer
from typing import TYPE_CHECKING
from app.theme import theme
from app.components import MouseWheelScrollableFrame
from ...level_editor_manager import level_editor_manager

if TYPE_CHECKING:
    from app.utils.selection.selection_element_group import SelectionElementGroup


class CanvasObjectsPanel(MouseWheelScrollableFrame):

    def __init__(self, master, layer_name: str, **kwargs):
        # Map max_height to height for CTkScrollableFrame consistency
        if "max_height" in kwargs:
            kwargs["height"] = kwargs.pop("max_height")

        self.layer_name = layer_name
        super().__init__(master, fg_color="transparent", **kwargs)

        self.configure(border_width=0)

        self.canvas_object_containers = self._create_canvas_object_containers()
        if not self.canvas_object_containers:
            return

        for i, container in enumerate(self.canvas_object_containers):
            row, column = divmod(i, 4)
            container.grid(row=row, column=column, sticky="nsew")

            # recursive scroll binding for children
            self.bind_scroll_events_recursively(container)

        selection_manager = SelectionManager(
            activate_callback=self._object_activate_callback,
            deactivate_callback=self._object_deactivate_callback,
        )

        def _on_select(frame: "CanvasObjectContainer"):
            level_editor_manager.selector.set_selection(
                self.layer_name + ".canvas_object", frame.canvas_object.name
            )

        populate_selection_manager(
            selection_manager,
            frames=self.canvas_object_containers,
            default_frame=self.canvas_object_containers[0],
            on_select=_on_select,
        )

        self.after(50, self._check_scroll_visibility)

    def _object_activate_callback(
        self, selection_element_group: "SelectionElementGroup"
    ):
        selection_element_group.frame.configure(
            border_width=1, border_color=theme.select_border_color
        )

    def _object_deactivate_callback(
        self, selection_element_group: "SelectionElementGroup"
    ):
        selection_element_group.frame.configure(border_width=0)

    def _create_canvas_object_containers(self):
        canvas_object_containers: list[CanvasObjectContainer] = []

        layer = level_editor_manager.objects_manager.get_layer(self.layer_name)
        for canvas_object in layer.canvas_objects.values():
            canvas_object_containers.append(CanvasObjectContainer(self, canvas_object))

        return canvas_object_containers
