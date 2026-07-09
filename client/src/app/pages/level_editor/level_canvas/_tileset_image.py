import numpy as np
from typing import TYPE_CHECKING
from PIL import Image

if TYPE_CHECKING:
    from pytiling import Tileset


class TilesetImage:
    def __init__(self, tileset: "Tileset"):
        self.tileset = tileset

        self.tile_images = np.empty(
            (tileset.grid_size[0], tileset.grid_size[1]),
            dtype=object,
        )

        self.tileset.for_tile_image(self._populate_tile_images)

    def _populate_tile_images(self, byte_data: bytes, x: int, y: int):
        """Populate the tile images array with PIL images."""
        self.tile_images[y, x] = self._create_image_from_bytes(byte_data)

    def _create_image_from_bytes(self, image_bytes: bytes):
        """Create PIL Image from a byte array."""
        tile_size = self.tileset.tile_size
        return Image.frombytes("RGBA", tile_size, image_bytes)

    def get_tile_image(self, display: tuple[int, int]) -> "Image.Image | None":
        """Get the PIL Image for a tile."""
        return self.tile_images[display[0], display[1]]
