import customtkinter as ctk
from .layer_container import LayerContainer
from src.app.components import SvgImage, SectionTitle
from app.theme import theme
from app.utils.selection import populate_selection_manager, SelectionManager
from loaders import level_loader
from ...level_editor_manager import level_editor_manager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from level.grid_map.editor_tilemap.editor_tilemap_layer import (
        EditorTilemapLayer,
    )
    from level.grid_map.world_objects_map.world_objects_layer.world_objects_layer import (
        WorldObjectsLayer,
    )


class LayersPanel(ctk.CTkFrame):

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")

        title = SectionTitle(self, text="Layers")
        title.pack(pady=8, side="top", anchor="w")

        self.layer_containers = self._create_layer_containers()
        default_layer_container = next(
            (
                container
                for container in self.layer_containers
                if container.layer_name == "platforms"
            ),
            None,
        )
        if default_layer_container is None:
            raise ValueError("Default layer container not found")

        self._pack_layer_containers()

        def _on_select(frame: "LayerContainer"):
            level_editor_manager.selector.set_selection("layer", frame.layer_name)

        populate_selection_manager(
            SelectionManager(),
            frames=self.layer_containers,
            default_frame=default_layer_container,
            on_select=_on_select,
        )

    def _pack_layer_containers(self):
        for layer_container in self.layer_containers:
            layer_container.pack(side="top", padx=8, anchor="w", fill="x")

    def _create_layer_containers(self):
        layer_containers: list[LayerContainer] = []

        for layer in level_loader.level.map.layers[::-1]:
            layer_containers.append(self._create_layer_container(layer))

        return layer_containers

    def _create_layer_container(
        self, layer: "EditorTilemapLayer | WorldObjectsLayer"
    ) -> LayerContainer:
        layer_icon_size = 24
        icon = SvgImage(
            svg_path=layer.icon_path,
            size=(layer_icon_size, layer_icon_size),
            fill=theme.icon_color,
        )
        container = LayerContainer(self, layer.name, icon.get_ctk_image())
        return container
