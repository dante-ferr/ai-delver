import sys
from pathlib import Path
import json

with open(Path(__file__).parent / "config.json", "r") as file:
    config = json.load(file)

TILEMAP_LAYER_NAMES = config["tilemap_layer_names"]
LAYER_ORDER = config["layer_order"]
START_MAP_WIDTH = config["start_map_width"]
START_MAP_HEIGHT = config["start_map_height"]
START_DELVER_POSITION = tuple(config["start_delver_position"])
START_GOAL_POSITION = tuple(config["start_goal_position"])
TILE_WIDTH = config["tile_width"]
TILE_HEIGHT = config["tile_height"]
MIN_GRID_SIZE = tuple(config["min_grid_size"])
MAX_GRID_SIZE = tuple(config["max_grid_size"])
LEVEL_SAVE_FOLDER_PATH = config["level_save_folder_path"]


def get_project_root() -> Path:
    """
    Determines the project's root directory, whether running from source
    or as a frozen executable (e.g., from PyInstaller).
    """
    if getattr(sys, "frozen", False):
        # If it is frozen, the root is the directory containing the executable.
        # sys.executable gives the path to MyGame.exe.
        application_path = Path(sys.executable)
        return application_path.parent
    else:
        # If it's not frozen, we are running from source code.
        # The project root is three levels up from this config file's location.
        # (src/ -> ai-delver-client/ -> ai-delver/)
        return Path(__file__).resolve().parent.parent.parent


PROJECT_ROOT = get_project_root()
ASSETS_PATH = PROJECT_ROOT / "assets"
