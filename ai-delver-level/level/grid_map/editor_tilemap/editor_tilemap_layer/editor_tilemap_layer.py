from pytiling import TilemapLayer


class EditorTilemapLayer(TilemapLayer):
    def __init__(self, name: str, tileset, icon_path: str):
        super().__init__(name, tileset)
        self.icon_path = icon_path

    def to_dict(self):
        """Serialize the layer to a dictionary with asset-relative paths."""
        from level.utils import to_asset_relative_path

        data = super().to_dict()
        data["__class__"] = "EditorTilemapLayer"
        # Overwrite absolute paths with relative ones
        data["icon_path"] = to_asset_relative_path(self.icon_path)
        data["tileset"] = to_asset_relative_path(self.tileset.tileset_path)
        return data
