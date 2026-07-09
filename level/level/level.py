from .level_toggler import LevelToggler
import json
import hashlib
import copy
from pytiling.serialization import map_from_dict
from pathlib import Path
from .config import LEVEL_SAVE_FOLDER_PATH
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from .grid_map import MixedMap


class Level:

    def __init__(
        self,
        mixed_map: "MixedMap",
    ):
        self.map = mixed_map

        self.toggler = LevelToggler()

        self._name = "My custom level"

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    def to_dict(self):
        return {
            "_name": self._name,
            "map": self.map.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict):
        map_obj = cast("MixedMap", map_from_dict(data["map"]))
        instance = cls(mixed_map=map_obj)
        instance.name = data["_name"]
        return instance

    def to_hash(self):
        """Generate a hash representation of the level."""
        """
        Generate a hash representation of the level.

        This is based on a JSON dump of the level's data, excluding any
        display-only properties (like 'icon_path' or a potential 'display' key)
        to ensure the hash only changes when gameplay-relevant data changes.
        """
        level_dict = self.to_dict()

        dict_for_hash = copy.deepcopy(level_dict)

        def _clean_dict_for_hash(d):
            """Recursively remove display-only keys from the dictionary."""
            if isinstance(d, dict):
                # As per the request, we filter out 'display' properties.
                # 'icon_path' is another such property found on layers.
                keys_to_remove = ["display", "icon_path"]
                for key in keys_to_remove:
                    d.pop(key, None)

                for value in d.values():
                    _clean_dict_for_hash(value)
            elif isinstance(d, list):
                for item in d:
                    _clean_dict_for_hash(item)

        _clean_dict_for_hash(dict_for_hash)

        # Serialize to a compact, sorted JSON string to ensure determinism.
        deterministic_json = json.dumps(
            dict_for_hash, sort_keys=True, separators=(",", ":")
        )

        hasher = hashlib.sha256()
        hasher.update(deterministic_json.encode("utf-8"))

        return hasher.hexdigest()

    @staticmethod
    def load(filepath: str):
        with open(filepath, "r") as file:
            data = json.load(file)
        level = Level.from_dict(data)
        return level

    @property
    def save_file_path(self):
        """
        Dynamically generates the save file path.
        """
        return Path(LEVEL_SAVE_FOLDER_PATH) / Path(self.name) / f"level.json"

    @property
    def same_name_saved(self):
        return self.save_file_path.parent.is_dir() if self.save_file_path else None

    def save(self, custom_path: Path | str | None = None):
        if not custom_path and not self.save_file_path:
            raise ValueError("Save file path is not set for the level.")

        if isinstance(custom_path, str):
            custom_path = Path(custom_path)

        path = custom_path or self.save_file_path
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w") as file:
            json.dump(self.to_dict(), file, indent=2, sort_keys=True)

    @property
    def issues(self):
        issues: list[str] = []

        essentials_layer = self.map.get_layer("essentials")
        delver = essentials_layer.has_element_named("delver")
        if not delver:
            issues.append("The delver needs to be placed on the level.")

        goal = essentials_layer.has_element_named("goal")
        if not goal:
            issues.append("The goal needs to be placed on the level.")

        return issues
