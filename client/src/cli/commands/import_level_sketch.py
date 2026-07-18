import json
import sys
from pathlib import Path

from level import LevelSketchError, LevelSketchImporter
from level.config import LEVEL_SAVE_FOLDER_PATH


def print_json(event: str, **kwargs):
    print(json.dumps({"event": event, **kwargs}), flush=True)


def run_import_level_sketch(args):
    """Import a simplified level sketch into a full editor level.json."""
    sketch_path = Path(args.from_path)
    force = bool(getattr(args, "force", False))

    try:
        print_json("info", message=f"Reading level sketch from '{sketch_path}'...")
        importer = LevelSketchImporter()
        level = importer.import_file(sketch_path)

        if getattr(args, "name", None):
            name = args.name.strip()
            if not name:
                print_json("error", message="--name cannot be empty.")
                sys.exit(1)
            level.name = name

        save_path = Path(LEVEL_SAVE_FOLDER_PATH) / level.name / "level.json"
        if save_path.is_file() and not force:
            print_json(
                "error",
                message=(
                    f"Level '{level.name}' already exists at '{save_path}'. "
                    "Pass --force to overwrite."
                ),
            )
            sys.exit(1)

        level.save()
        print_json(
            "level_imported",
            name=level.name,
            path=str(level.save_file_path),
            grid_size=[level.map.grid_size[0], level.map.grid_size[1]],
            message=f"Imported sketch into level save '{level.name}'.",
        )
    except LevelSketchError as exc:
        print_json("error", message=str(exc))
        sys.exit(1)
    except Exception as exc:
        print_json("error", message=f"Failed to import level sketch: {exc}")
        sys.exit(1)
