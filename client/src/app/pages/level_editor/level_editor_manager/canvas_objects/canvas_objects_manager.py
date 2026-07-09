from ._canvas_objects_factory import CanvasObjectsFactory
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from .canvas_object import CanvasObject
    from level import Level
    from level.grid_map import MixedMap
    from level.grid_map.world_objects_map.world_objects_layer import WorldObjectsLayer
    from ._canvas_objects_layer import CanvasObjectsLayer


class CanvasObjectsManager:
    def __init__(self):
        self.factory = CanvasObjectsFactory()
        self.layers = self.factory.create_layers()
        self._layers_dict = {layer.name: layer for layer in self.layers}
        self._level: "Level | None" = None

    @property
    def level(self):
        if self._level is None:
            raise ValueError("Level not assigned to CanvasObjectsManager.")
        return self._level

    @level.setter
    def level(self, level: "Level"):
        self._level = level

    def assign_level_to_objects(self, level: "Level"):
        self.level = level

        platform_co = self.get_canvas_object("platform")
        platform_co.create_element_callback = self._create_platform_callback
        platform_co.remove_element_callback = self._remove_platform_callback

        self._assign_layer_to_world_canvas_object("delver")
        self._assign_layer_to_variated_world_canvas_object("goal")

    def _create_platform_callback(self, position: tuple[int, int]):
        from state_managers import canvas_state_manager

        self.level.map.tilemap.create_basic_platform_at(
            position,
            dynamic_resizing=cast(
                bool, canvas_state_manager.get_value("dynamic_resizing")
            ),
            apply_formatting=True,
        )

    def _remove_platform_callback(self, position: tuple[int, int]):
        from state_managers import canvas_state_manager

        self.level.map.tilemap.remove_platform_at(
            position,
            dynamic_resizing=cast(
                bool, canvas_state_manager.get_value("dynamic_resizing")
            ),
            apply_formatting=True,
        )

    def _assign_layer_to_world_canvas_object(self, object_name: str):
        canvas_object = self.get_canvas_object(object_name)
        canvas_object.create_element_callback = (
            lambda position: self._create_world_object_at(position, canvas_object)
        )

    def _assign_layer_to_variated_world_canvas_object(self, world_object_name: str):
        for variation in self.factory.VARIATIONS[world_object_name]:
            canvas_object = self.get_canvas_object(variation)
            canvas_object.create_element_callback = lambda position, co=canvas_object: self._create_variated_world_object_at(
                position, co
            )

    def _create_world_object_at(
        self, position: tuple[int, int], canvas_object: "CanvasObject"
    ):
        layer = cast(
            "WorldObjectsLayer", self._get_grid_layer_of_canvas_object(canvas_object)
        )
        args = canvas_object.world_object_args
        world_object = layer.create_world_object_at(position, **args)

        return world_object

    def _create_variated_world_object_at(
        self,
        position: tuple[int, int],
        canvas_object: "CanvasObject",
    ):
        layer = cast(
            "WorldObjectsLayer",
            self._get_grid_layer_of_canvas_object(canvas_object),
        )

        variations = self.factory.VARIATIONS[canvas_object.world_object_args["name"]]
        for element in layer.get_elements(
            *[v for v in variations if v != canvas_object.name]
        ):
            layer.remove_element(element)

        self._create_world_object_at(position, canvas_object)

    def get_canvas_object(self, canvas_object_name: str) -> "CanvasObject":
        return self.canvas_objects[canvas_object_name]

    def _get_grid_layer_of_canvas_object(self, canvas_object: "CanvasObject"):
        if canvas_object.layer is None:
            raise ValueError(
                f"Canvas object '{canvas_object.name}' has no layer assigned."
            )

        layer_name = canvas_object.layer.name
        return self.level.map.get_layer(layer_name)

    def get_layer(self, layer_name: str):
        return self._layers_dict[layer_name]

    @property
    def canvas_objects(self):
        canvas_objects: dict[str, "CanvasObject"] = {}

        for layer in self.layers:
            layer = cast("CanvasObjectsLayer", layer)
            for canvas_object in layer.canvas_objects.values():
                canvas_objects[canvas_object.name] = canvas_object

        return canvas_objects
