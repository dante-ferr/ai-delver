from pathlib import Path
import json
import shutil
from .config import AGENT_SAVE_FOLDER_PATH, SESSION_STORAGE_KEY
from runtime.episode_trajectory import TrajectoryLoader


class Agent:
    def __init__(self, name: str, storage_key: str | None = None):
        self.name = name
        self._storage_key = storage_key or name
        self.trajectory_loader = TrajectoryLoader(self._storage_key)

    @property
    def storage_key(self) -> str:
        """Folder name under the agents save root used for disk I/O."""
        return self._storage_key

    def rebind_storage(self, storage_key: str) -> None:
        """Point trajectory/weights paths at a different on-disk folder."""
        self._storage_key = storage_key
        self.trajectory_loader = TrajectoryLoader(storage_key)

    @property
    def is_session(self) -> bool:
        return self._storage_key == SESSION_STORAGE_KEY

    @property
    def same_name_saved(self):
        return self.named_save_dir.is_dir() if self.named_save_dir else None

    @property
    def named_save_dir(self) -> Path | None:
        """Directory for the display-named agent (not the session workspace)."""
        if not AGENT_SAVE_FOLDER_PATH:
            return None
        return Path(AGENT_SAVE_FOLDER_PATH) / Path(self.name)

    def to_dict(self) -> dict:
        return {"name": self.name}

    def write_meta(self, *, extra: dict | None = None, drop_keys: list[str] | None = None) -> None:
        """Write agent.json for this workspace, merging ``extra`` fields."""
        if not self.save_file_path:
            from .exceptions import AgentError

            raise AgentError("Save file path is not set for the agent.")

        self.save_file_path.parent.mkdir(parents=True, exist_ok=True)
        data: dict = {}
        if self.save_file_path.is_file():
            try:
                with open(self.save_file_path, "r") as file:
                    loaded = json.load(file)
                if isinstance(loaded, dict):
                    data = loaded
            except (OSError, json.JSONDecodeError):
                data = {}
        data.update(self.to_dict())
        if extra:
            data.update(extra)
        for key in drop_keys or []:
            data.pop(key, None)
        with open(self.save_file_path, "w") as file:
            json.dump(data, file, indent=2, sort_keys=True)

    @classmethod
    def from_dict(cls, data: dict, storage_key: str | None = None) -> "Agent":
        return cls(data["name"], storage_key=storage_key)

    @staticmethod
    def load(filepath: str | Path, storage_key: str | None = None) -> "Agent":
        try:
            with open(filepath, "r") as file:
                data = json.load(file)
            return Agent.from_dict(data, storage_key=storage_key)
        except Exception as e:
            from .exceptions import AgentLoadError

            raise AgentLoadError(f"Failed to load agent from {filepath}: {e}") from e

    @classmethod
    def persist(
        cls,
        name: str,
        *,
        from_name: str | None = None,
        force: bool = False,
    ) -> "Agent":
        """Save an agent, optionally copying another agent's folder first.

        When ``from_name`` differs from ``name`` and the source directory exists,
        the entire agent folder (weights, trajectories, checkpoints, etc.) is
        copied into the destination before writing ``agent.json``.
        """
        name = name.strip()
        if not name:
            from .exceptions import AgentError

            raise AgentError("Agent name cannot be empty.")
        if name == SESSION_STORAGE_KEY:
            from .exceptions import AgentError

            raise AgentError(f"'{SESSION_STORAGE_KEY}' is reserved for the live session workspace.")

        agent = cls(name)
        source_name = (from_name or name).strip()

        if source_name and source_name != name:
            agent._copy_folder_from(source_name, force=force)

        # Keep UI prefs from the copied/existing agent.json; strip session-only keys.
        agent.write_meta(drop_keys=["bound_name"])
        return agent

    def _copy_folder_from(self, source_name: str, force: bool = False) -> None:
        if not AGENT_SAVE_FOLDER_PATH or not self.save_file_path:
            from .exceptions import AgentError

            raise AgentError("Save file path is not set for the agent.")

        source_dir = Path(AGENT_SAVE_FOLDER_PATH) / source_name
        dest_dir = self.save_file_path.parent

        if not source_dir.is_dir():
            from .exceptions import AgentError

            raise AgentError(f"Source agent '{source_name}' was not found at '{source_dir}'.")

        if source_dir.resolve() == dest_dir.resolve():
            return

        if dest_dir.exists():
            if not force:
                from .exceptions import AgentError

                raise AgentError(
                    f"Agent '{self.name}' already exists at '{dest_dir}'. "
                    "Pass --force to overwrite."
                )
            shutil.rmtree(dest_dir)

        shutil.copytree(source_dir, dest_dir)

    def save(self):
        if not self.save_file_path:
            from .exceptions import AgentError

            raise AgentError("Save file path is not set for the agent.")

        self.save_file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.save_file_path, "w") as file:
            json.dump(self.to_dict(), file, indent=2, sort_keys=True)

    @property
    def workspace_dir(self) -> Path | None:
        if not AGENT_SAVE_FOLDER_PATH:
            return None
        return Path(AGENT_SAVE_FOLDER_PATH) / Path(self._storage_key)

    @property
    def save_file_path(self):
        """Path to agent.json inside the active workspace folder."""
        workspace = self.workspace_dir
        return workspace / "agent.json" if workspace else None

    @property
    def weights_path(self) -> Path | None:
        """Path to policy weights inside the active workspace folder."""
        workspace = self.workspace_dir
        return workspace / "model_weights.zip" if workspace else None
