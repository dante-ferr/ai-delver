from ._canvas_objects_layer import CanvasObjectsLayer
from src.config import config
from .canvas_object import CanvasObject
from typing import Any


class CanvasObjectsFactory:
    VARIATIONS = {
        "goal": ["battery_snack", "oil_drink", "uranium_cake"],
    }

    def create_layers(self):
        platforms = CanvasObjectsLayer("platforms")
        platforms.add_canvas_object(self._create_canvas_object("platform"))

        essentials = CanvasObjectsLayer("essentials")
        essentials.add_canvas_object(self._create_canvas_object("delver", unique=True))
        for canvas_object in self._create_variated_canvas_objects("goal", unique=True):
            essentials.add_canvas_object(canvas_object)

        return [platforms, essentials]

    def _create_variated_canvas_objects(
        self, world_object_name: str, **world_object_args
    ):
        canvas_objects = []
        variations = self.VARIATIONS.get(world_object_name, [])

        for variation in variations:
            canvas_object = self._create_canvas_object(
                variation,
                path=str(
                    config.ASSETS_PATH
                    / f"img/representations/{world_object_name}/{variation}.png"
                ),
                name=world_object_name,
                tags=[f"variation_{variation}"],
                **world_object_args,
            )
            canvas_objects.append(canvas_object)

        return canvas_objects

    def _create_canvas_object(
        self,
        canvas_object_name: str,
        path: str | None = None,
        **world_object_args,
    ):
        if world_object_args.get("name") is None:
            world_object_args["name"] = canvas_object_name

        if path is None:
            path = str(
                config.ASSETS_PATH / f"img/representations/{canvas_object_name}.png"
            )

        return CanvasObject(canvas_object_name, path, world_object_args)
