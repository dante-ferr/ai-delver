from ._canvas_objects_layer import CanvasObjectsLayer
from src.config import config
from .canvas_object import CanvasObject
from level import resolve_editor_object_image, world_object_size


class CanvasObjectsFactory:
    VARIATIONS = {
        "goal": ["battery_snack", "oil_drink", "uranium_cake"],
    }

    def create_layers(self):
        platforms = CanvasObjectsLayer("platforms")
        platforms.add_canvas_object(self._create_canvas_object("platform"))

        traps = CanvasObjectsLayer("traps")
        traps.add_canvas_object(
            self._create_canvas_object("spike_trap", master_name="platform")
        )

        essentials = CanvasObjectsLayer("essentials")
        essentials.add_canvas_object(
            self._create_canvas_object(
                "delver",
                unique=True,
                size=world_object_size("delver"),
                image_fit="native",
            )
        )
        for canvas_object in self._create_variated_canvas_objects("goal", unique=True):
            essentials.add_canvas_object(canvas_object)

        return [platforms, traps, essentials]

    def _create_variated_canvas_objects(
        self, world_object_name: str, **world_object_args
    ):
        canvas_objects = []
        variations = self.VARIATIONS.get(world_object_name, [])
        size = world_object_size(world_object_name)

        for variation in variations:
            canvas_object = self._create_canvas_object(
                variation,
                path=str(
                    resolve_editor_object_image(
                        config.ASSETS_PATH,
                        world_object_name,
                        variation=variation,
                    )
                ),
                name=world_object_name,
                tags=[f"variation_{variation}"],
                size=size,
                **world_object_args,
            )
            canvas_objects.append(canvas_object)

        return canvas_objects

    def _create_canvas_object(
        self,
        canvas_object_name: str,
        path: str | None = None,
        image_fit: str = "stretch",
        **world_object_args,
    ):
        if world_object_args.get("name") is None:
            world_object_args["name"] = canvas_object_name

        if path is None:
            path = str(
                resolve_editor_object_image(config.ASSETS_PATH, canvas_object_name)
            )

        return CanvasObject(
            canvas_object_name,
            path,
            world_object_args,
            image_fit=image_fit,  # type: ignore[arg-type]
        )
