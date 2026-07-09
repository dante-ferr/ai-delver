# filename: _trajectory_metadata_manager.py

import logging
import json
from ._get_trajectory_dir import get_trajectory_dir
from typing import TYPE_CHECKING
import aiofiles

if TYPE_CHECKING:
    from pathlib import Path


class TrajectoryMetadataManager:
    """
    Manages the metadata file for an agent's trajectories asynchronously.
    """

    METADATA_FILE = "metadata.json"

    def __init__(self, agent_name: str):
        self.agent_name = agent_name

    async def write_metadata(self, metadata: dict):
        """Asynchronously writes the metadata to the trajectory directory."""
        metadata_path = self.trajectory_dir / self.METADATA_FILE
        json_content = json.dumps(metadata, indent=4)
        async with aiofiles.open(metadata_path, "w") as f:
            await f.write(json_content)

    async def read_metadata(self) -> dict:
        """Asynchronously reads the metadata file from the trajectory directory."""
        metadata_path = self.trajectory_dir / self.METADATA_FILE
        try:
            async with aiofiles.open(metadata_path, "r") as f:
                content = await f.read()
                # json.loads is a sync, CPU-bound operation.
                return json.loads(content)
        except FileNotFoundError:
            # If the file doesn't exist, return a default dictionary.
            return {"trajectory_count": 0, "stats": {"amount": 0, "victories": 0}}
        except json.JSONDecodeError:
            logging.warning(f"Could not decode {metadata_path}, resetting.")
            return {"trajectory_count": 0, "stats": {"amount": 0, "victories": 0}}

    @property
    def trajectory_dir(self) -> "Path":
        """Returns the path to the trajectory directory. This is not I/O bound."""
        return get_trajectory_dir(self.agent_name)
