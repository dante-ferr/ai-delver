import json
import pathlib

current_dir = pathlib.Path(__file__).parent
with open(current_dir / "config.json", "r") as f:
    config = json.load(f)

AGENT_SAVE_FOLDER_PATH = config["agent_save_folder_path"]
