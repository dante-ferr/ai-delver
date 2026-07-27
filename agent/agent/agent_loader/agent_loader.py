from ._agent_factory import AgentFactory
from pathlib import Path
import json
import logging
import shutil
from ..agent import Agent
from ..config import AGENT_SAVE_FOLDER_PATH, SESSION_STORAGE_KEY
from typing import Callable, cast


class AgentLoader:
    """Owns the live agent workspace (session) and optional binding to a named save."""

    def __init__(self):
        self.factory = AgentFactory()
        self._bound_name: str | None = None
        self._autosave: bool = False
        self._early_stop: bool = False
        self._live: bool = True
        self._dirty: bool = False
        self._dirty_listeners: list[Callable[[bool], None]] = []
        self._prefs_listeners: list[Callable[[], None]] = []
        self._create_new_agent()

    def load_agent(self, path: str | Path):
        """Load a named agent directory into the live session (or bind directly if autosave)."""
        if type(path) == str:
            path = Path(path)
        path = cast(Path, path)

        if not path.is_dir():
            from ..exceptions import AgentLoadError

            raise AgentLoadError(f"Agent directory not found: {path}")
        if path.name == SESSION_STORAGE_KEY:
            from ..exceptions import AgentLoadError

            raise AgentLoadError("Cannot load the reserved session workspace as a named agent.")

        file_path = path / "agent.json"
        prefs = self._read_prefs_file(file_path if file_path.is_file() else None)
        if file_path.is_file():
            Agent.load(file_path)  # validate

        name = path.name
        # Apply loaded prefs before deciding storage (autosave may bind directly).
        self._early_stop = bool(prefs.get("early_stop", False))
        self._live = bool(prefs.get("live", True))
        want_autosave = bool(prefs.get("autosave", False))

        if want_autosave:
            self._agent = Agent(name, storage_key=name)
            if not file_path.is_file():
                self._agent.save()
            self._bound_name = name
            self._autosave = True
        else:
            self._replace_session_from(path)
            self._agent = Agent(name, storage_key=SESSION_STORAGE_KEY)
            self._bound_name = name
            self._autosave = False
            self._write_session_meta()

        self._sync_prefs_to_app()
        self._notify_prefs_listeners()
        self._set_dirty(False)
        return self.agent

    @property
    def agent(self):
        if self._agent is None:
            from ..exceptions import AgentLoadError
            raise AgentLoadError("The agent doesn't exist.")
        return self._agent

    @property
    def persisted_name(self) -> str | None:
        """Named agent this session is bound to, if any."""
        return self._bound_name

    @property
    def bound_name(self) -> str | None:
        return self._bound_name

    @property
    def storage_key(self) -> str:
        """Folder key train/save I/O should use right now."""
        if self._autosave and self._bound_name:
            return self._bound_name
        return SESSION_STORAGE_KEY

    @property
    def autosave(self) -> bool:
        return self._autosave

    @property
    def early_stop(self) -> bool:
        return self._early_stop

    @property
    def live(self) -> bool:
        return self._live

    @property
    def dirty(self) -> bool:
        return self._dirty

    def mark_persisted(self, name: str) -> None:
        self._bound_name = name

    def mark_dirty(self) -> None:
        """Session has unsaved changes relative to the bound named agent (or is unbound)."""
        if self._autosave and self._bound_name:
            # Writes already land on the named agent.
            self._set_dirty(False)
            return
        self._set_dirty(True)

    def clear_dirty(self) -> None:
        self._set_dirty(False)

    def add_dirty_listener(self, callback: Callable[[bool], None]) -> None:
        self._dirty_listeners.append(callback)

    def remove_dirty_listener(self, callback: Callable[[bool], None]) -> None:
        if callback in self._dirty_listeners:
            self._dirty_listeners.remove(callback)

    def add_prefs_listener(self, callback: Callable[[], None]) -> None:
        self._prefs_listeners.append(callback)

    def remove_prefs_listener(self, callback: Callable[[], None]) -> None:
        if callback in self._prefs_listeners:
            self._prefs_listeners.remove(callback)

    def set_autosave(self, enabled: bool) -> None:
        """Enable/disable autosave. Enabling without a bind requires a prior save."""
        enabled = bool(enabled)
        if enabled == self._autosave:
            self._persist_ui_prefs()
            return

        if enabled:
            if not self._bound_name:
                from ..exceptions import AgentError

                raise AgentError(
                    "Save the agent once before enabling auto-save "
                    "(auto-save needs a named agent to bind to)."
                )
            # Sync session workspace into the bound agent, then write there directly.
            if self.agent.storage_key == SESSION_STORAGE_KEY:
                Agent.persist(self._bound_name, from_name=SESSION_STORAGE_KEY, force=True)
            self._agent.name = self._bound_name
            self._agent.rebind_storage(self._bound_name)
            self._autosave = True
            self._set_dirty(False)
        else:
            # Snapshot the bound agent back into the session workspace and keep editing there.
            if self._bound_name:
                self._replace_session_from(
                    Path(AGENT_SAVE_FOLDER_PATH) / self._bound_name
                )
            self._agent.rebind_storage(SESSION_STORAGE_KEY)
            self._autosave = False

        self._persist_ui_prefs()
        self._notify_prefs_listeners()

    def set_early_stop(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if enabled == self._early_stop:
            return
        self._early_stop = enabled
        self._sync_prefs_to_app()
        self._persist_ui_prefs()
        self._notify_prefs_listeners()

    def set_live(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if enabled == self._live:
            return
        self._live = enabled
        self._persist_ui_prefs()
        self._notify_prefs_listeners()

    def bind_after_save(self, name: str) -> None:
        """Called after a successful Save into a named agent folder."""
        self._bound_name = name
        self._agent.name = name
        if self._autosave:
            self._agent.rebind_storage(name)
        else:
            self._agent.rebind_storage(SESSION_STORAGE_KEY)
            # Keep session contents aligned with what was just saved.
            named_dir = Path(AGENT_SAVE_FOLDER_PATH) / name
            if named_dir.is_dir():
                self._replace_session_from(named_dir)
                self._agent = Agent(name, storage_key=SESSION_STORAGE_KEY)
        self._persist_ui_prefs()
        self._set_dirty(False)

    def _create_new_agent(self):
        self._agent: "Agent" = self.factory.create_agent()
        self._bound_name = None
        self._autosave = False
        self._early_stop = False
        self._live = True
        self._ensure_session_workspace()
        self._restore_session_meta()
        self._apply_storage_for_flags()
        self._sync_prefs_to_app()
        self._set_dirty(False)

    def _ensure_session_workspace(self) -> None:
        if not AGENT_SAVE_FOLDER_PATH:
            return
        session_dir = Path(AGENT_SAVE_FOLDER_PATH) / SESSION_STORAGE_KEY
        session_dir.mkdir(parents=True, exist_ok=True)

    def _session_meta_path(self) -> Path | None:
        if not AGENT_SAVE_FOLDER_PATH:
            return None
        return Path(AGENT_SAVE_FOLDER_PATH) / SESSION_STORAGE_KEY / "agent.json"

    def _ui_prefs_payload(self) -> dict:
        return {
            "autosave": self._autosave,
            "early_stop": self._early_stop,
            "live": self._live,
        }

    def _persist_ui_prefs(self) -> None:
        """Write UI prefs into the session meta and, when bound+autosave, the named agent."""
        self._write_session_meta()
        if self._autosave and self._bound_name and AGENT_SAVE_FOLDER_PATH:
            named = Agent(self._bound_name, storage_key=self._bound_name)
            named.write_meta(extra=self._ui_prefs_payload(), drop_keys=["bound_name"])

    def _write_session_meta(self) -> None:
        path = self._session_meta_path()
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "name": self._agent.name,
            "bound_name": self._bound_name,
            **self._ui_prefs_payload(),
        }
        with open(path, "w") as file:
            json.dump(payload, file, indent=2, sort_keys=True)

    def _read_prefs_file(self, path: Path | None) -> dict:
        if path is None or not path.is_file():
            return {}
        try:
            with open(path, "r") as file:
                data = json.load(file)
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _restore_session_meta(self) -> None:
        path = self._session_meta_path()
        if path is None or not path.is_file():
            self._write_session_meta()
            return
        data = self._read_prefs_file(path)
        if not data:
            self._write_session_meta()
            return

        name = str(data.get("name") or self._agent.name).strip() or self._agent.name
        bound = data.get("bound_name")
        bound_name = str(bound).strip() if bound else None
        if bound_name == SESSION_STORAGE_KEY:
            bound_name = None
        autosave = bool(data.get("autosave", False))

        self._agent.name = name
        self._bound_name = bound_name
        self._autosave = autosave and bound_name is not None
        self._early_stop = bool(data.get("early_stop", False))
        self._live = bool(data.get("live", True))

    def _apply_storage_for_flags(self) -> None:
        key = self.storage_key
        if (
            key != SESSION_STORAGE_KEY
            and AGENT_SAVE_FOLDER_PATH
            and not (Path(AGENT_SAVE_FOLDER_PATH) / key).is_dir()
        ):
            # Bound folder missing — fall back to session.
            logging.warning(
                "Bound agent '%s' missing on disk; resuming session workspace.", key
            )
            self._autosave = False
            key = SESSION_STORAGE_KEY
        self._agent.rebind_storage(key)
        self._write_session_meta()

    def _replace_session_from(self, source_dir: Path) -> None:
        if not AGENT_SAVE_FOLDER_PATH:
            return
        session_dir = Path(AGENT_SAVE_FOLDER_PATH) / SESSION_STORAGE_KEY
        if source_dir.resolve() == session_dir.resolve():
            return
        if session_dir.exists():
            shutil.rmtree(session_dir)
        shutil.copytree(source_dir, session_dir)

    def _sync_prefs_to_app(self) -> None:
        try:
            from state_managers import training_state_manager

            training_state_manager.early_stop = self._early_stop
        except Exception:
            pass

    def _notify_prefs_listeners(self) -> None:
        for listener in list(self._prefs_listeners):
            listener()

    def _set_dirty(self, dirty: bool) -> None:
        dirty = bool(dirty)
        if dirty == self._dirty:
            return
        self._dirty = dirty
        for listener in list(self._dirty_listeners):
            listener(dirty)
