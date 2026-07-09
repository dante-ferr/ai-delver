from ._tileset_image import TilesetImage
from typing import Literal, TYPE_CHECKING, cast
from loaders import level_loader
from ._world_objects_image import WorldObjectsImage
from pytiling import Tile
from level.grid_map.world_objects_map.world_object import (
    WorldObjectRepresentation,
)
from PIL import ImageTk, Image

if TYPE_CHECKING:
    from pytiling import Tileset, GridElement, GridMap
    from PIL.ImageTk import PhotoImage
    from .level_canvas import LevelCanvas


class CanvasGridElementRenderer:
    """
    Manages rendering, caching, and manipulation of all grid-based visual elements
    (tiles and world objects) on the LevelCanvas. It handles drawing, erasing,
    and updating elements in response to model changes and user interactions like
    zooming.
    """
    def __init__(self, canvas: "LevelCanvas"):
        self.canvas = canvas

        self._add_event_listeners()

        self.photo_image_cache: dict[tuple[int, int, int], ImageTk.PhotoImage] = {}
        self._initialize_tileset_images()
        self.world_objects_image = WorldObjectsImage()

        self.pil_image_registry: dict[int, Image.Image] = {}

    def _add_event_listeners(self):
        """Binds methods to events from the level's tilemap and world objects map."""
        level_loader.level.map.tilemap.on_layer_event(
            "element_created", self._handle_tile_created
        )
        level_loader.level.map.tilemap.on_layer_event(
            "tile_formatted", self._handle_tile_formatted
        )
        level_loader.level.map.tilemap.on_layer_event(
            "element_removed", self._handle_element_removed
        )

        level_loader.level.map.world_objects_map.on_layer_event(
            "element_created", self._handle_world_object_created
        )
        level_loader.level.map.world_objects_map.on_layer_event(
            "element_removed", self._handle_element_removed
        )

    def _handle_tile_created(self, sender, element: "GridElement"):
        """Callback to draw a tile when it's created in the model."""
        self.draw_tile(cast("Tile", element))

    def _handle_tile_formatted(self, sender, tile: "Tile"):
        """Callback to redraw a tile when its properties (e.g., display) change."""
        self.draw_tile(tile)

    def _handle_element_removed(self, sender, element: "GridElement", layer_name: str):
        """Callback to erase a grid element when it's removed from the model."""
        self.erase_grid_element(element, layer_name)

    def _handle_world_object_created(self, sender, element: "GridElement"):
        """Callback to draw a world object when it's created in the model."""
        self.draw_world_object(cast("WorldObjectRepresentation", element))

    def _initialize_tileset_images(self):
        """Create a dictionary of TilesetImage objects for each tileset."""
        self.tileset_images: dict[Tileset, TilesetImage] = {}
        for tileset in level_loader.level.map.tilemap.tilesets:
            self.tileset_images[tileset] = TilesetImage(tileset)

    def handle_reduction(self, removed_positions: "GridMap.RemovedPositions"):
        for position in removed_positions:
            pos = self.canvas.camera.world_to_canvas_grid_pos(position)
            self.canvas.delete(f"position={pos[0]},{pos[1]}")

    def erase_all_grid_elements(self):
        """Erase all tiles on the canvas."""
        self.canvas.delete("grid_element")

    def draw_all_grid_elements(self):
        """Draw all tiles on the canvas."""
        for tile in level_loader.level.map.tilemap.all_tiles:
            self.draw_tile(tile)
        for world_object in level_loader.level.map.world_objects_map.all_world_objects:
            self.draw_world_object(world_object)

    def draw_tile(self, tile: "Tile"):
        """Draw a tile on the canvas."""
        self._draw_grid_element(
            tile, self.tileset_images[tile.layer.tileset].get_tile_image(tile.display)
        )

    def draw_world_object(self, world_object: "WorldObjectRepresentation"):
        """Draw a world object on the canvas"""
        pil_image = self.world_objects_image.get_image(world_object.canvas_object_name)
        self._draw_grid_element(world_object, pil_image)

    def get_scaled_photo_image(self, pil_image: "Image.Image") -> "PhotoImage":
        """
        Creates or retrieves from cache a PhotoImage for a given PIL Image at the current canvas zoom level.
        """
        tile_width, tile_height = level_loader.level.map.tile_size
        scaled_width = int(tile_width * self.canvas.camera.zoom_level)
        scaled_height = int(tile_height * self.canvas.camera.zoom_level)

        cache_key = (id(pil_image), scaled_width, scaled_height)
        photo_image = self.photo_image_cache.get(cache_key)

        if photo_image is None:
            # Use NEAREST for a crisp, pixel-art style during scaling.
            resized_image = pil_image.resize(
                (scaled_width, scaled_height),
                Image.NEAREST,  # Type is ignored because Image.NEAREST actually exists # type: ignore
            )
            photo_image = ImageTk.PhotoImage(resized_image)
            self.photo_image_cache[cache_key] = photo_image
        return photo_image

    def _draw_grid_element(
        self, element: "GridElement", pil_image: "Image.Image | None"
    ):
        """Draw a grid element on the canvas, applying zoom and offset."""
        if pil_image is None:
            return

        self.pil_image_registry[id(pil_image)] = pil_image

        photo_image = self.get_scaled_photo_image(pil_image)

        canvas_grid_pos = self.canvas.camera.world_to_canvas_grid_pos(element.position)
        tile_w, tile_h = self.canvas.tile_size

        screen_x = canvas_grid_pos[0] * tile_w
        screen_y = canvas_grid_pos[1] * tile_h

        tags_to_find = self._get_grid_element_tags(element, "element's")
        items = self.canvas.items_with_tags(tags_to_find[0], tags_to_find[1])

        if items:
            # Item exists, so update it
            item_id = items[0]
            self.canvas.coords(item_id, screen_x, screen_y)
            # Also update the tags to ensure the pil_id is correct
            self.canvas.itemconfig(
                item_id,
                image=photo_image,
                tags=self._get_grid_element_tags(element, pil_image=pil_image),
            )
        else:
            # Item does not exist, so create it
            self.canvas.create_image(
                screen_x,
                screen_y,
                image=photo_image,
                anchor="nw",
                tags=self._get_grid_element_tags(element, pil_image=pil_image),
            )

        self.canvas.update_draw_order()

    def erase_grid_element(
        self,
        element: "GridElement",
        layer_name: str | Literal["element's"] = "element's",
    ):
        """Erase a grid element from the canvas only if it has both the position and layer tags."""
        for item in self.canvas.items_with_tags(
            *self._get_grid_element_tags(element, layer_name)
        ):
            self.canvas.delete(item)

    def rescale_and_reposition_item(
        self,
        item_id: int,
        old_zoom: float,
        origin_x: int,
        origin_y: int,
    ):
        """Resizes and repositions a single canvas item based on a zoom change."""
        # Get the original PIL Image for this item using its ID tag.
        tags = self.canvas.gettags(item_id)
        pil_id_tag = next((tag for tag in tags if tag.startswith("pil_id=")), None)
        if not pil_id_tag:
            return

        pil_id = int(pil_id_tag.split("=")[1])
        pil_image = self.pil_image_registry.get(pil_id)
        if not pil_image:
            return

        # Get a new, scaled PhotoImage and update the canvas item.
        new_photo_image = self.get_scaled_photo_image(pil_image)
        self.canvas.itemconfig(item_id, image=new_photo_image)

        # Get grid position and calculate new screen coordinates relative to the zoom origin.
        grid_pos = self._get_position_from_tag(item_id)
        if not grid_pos:
            return

        new_x, new_y = self.canvas.camera.calculate_zoomed_coords(
            grid_pos, old_zoom, origin_x, origin_y
        )
        self.canvas.coords(item_id, new_x, new_y)

    def _get_image_for_element(self, element: "GridElement") -> "Image.Image | None":
        """Helper to get the correct image for any grid element."""
        if isinstance(element, Tile):
            tile = cast("Tile", element)
            return self.tileset_images[element.layer.tileset].get_tile_image(
                tile.display
            )
        elif isinstance(element, WorldObjectRepresentation):
            world_object = cast("WorldObjectRepresentation", element)
            return self.world_objects_image.get_image(world_object.canvas_object_name)
        return None

    def _get_position_from_tag(self, item_id: int) -> tuple[int, int] | None:
        """Extracts canvas grid coordinates from an item's 'position' tag."""
        tags = self.canvas.gettags(item_id)
        pos_tag = next((tag for tag in tags if tag.startswith("position=")), None)
        if not pos_tag:
            return None

        try:
            canvas_grid_x, canvas_grid_y = map(int, pos_tag.split("=")[1].split(","))
            return canvas_grid_x, canvas_grid_y
        except (ValueError, IndexError):
            return None

    def _get_grid_element_tags(
        self,
        element: "GridElement",
        layer_name: str | Literal["element's"] = "element's",
        pil_image: "Image.Image | None" = None,
    ):
        """Return the tag for a grid element."""
        canvas_grid_x, canvas_grid_y = self.canvas.camera.world_to_canvas_grid_pos(
            element.position
        )

        position_tag = f"position={canvas_grid_x},{canvas_grid_y}"
        if layer_name == "element's":
            layer = element.layer
            layer_tag = f"layer={layer.name}"
        else:
            layer_tag = f"layer={layer_name}"

        grid_element_tag = "grid_element"

        if pil_image:
            image_id_tag = f"pil_id={id(pil_image)}"
            return (position_tag, layer_tag, grid_element_tag, image_id_tag)

        return (position_tag, layer_tag, grid_element_tag)
