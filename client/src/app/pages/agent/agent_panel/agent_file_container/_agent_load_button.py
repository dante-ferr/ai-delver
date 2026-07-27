import customtkinter as ctk
from app.components import FileLoaderOverlay, LoadButton
from app.fonts import app_font
from agent.config import AGENT_SAVE_FOLDER_PATH, SESSION_STORAGE_KEY
from app.components.overlay.file_loader_overlay.file_loader_overlay_spawner import (
    FileLoaderOverlaySpawner,
)
from state_managers import training_state_manager
from src.config import config


class _AgentLoaderOverlay(FileLoaderOverlay):
    def _load(self):
        import subprocess
        import sys
        import json
        import os
        from loaders import agent_loader
        from app_manager import app_manager
        from bootstrap import PROJECT_ROOT
        from app.components.overlay.message_overlay import MessageOverlay

        agent_path = self._get_file_path()
        client_dir = os.path.abspath(os.path.join(PROJECT_ROOT, ".."))

        cmd = [
            sys.executable, "src/cli/main.py",
            "load-agent",
            "--path", str(agent_path)
        ]

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=client_dir
            )
            stdout_out, stderr_out = process.communicate()

            if process.returncode != 0:
                raise RuntimeError(stderr_out.strip() or f"Subprocess exited with code {process.returncode}")

            event_data = {}
            for line in stdout_out.splitlines():
                if line.strip().startswith("{"):
                    try:
                        event_data = json.loads(line)
                        break
                    except json.JSONDecodeError:
                        continue

            if event_data.get("event") == "agent_loaded":
                super()._load()
                agent_loader.load_agent(agent_path)
                training_state_manager.clear_nerd_metrics()
                training_state_manager.all_time_loss_history = []
                training_state_manager.all_time_return_history = []
                training_state_manager.all_time_step_history = []
                app_manager.editor_app.restart_all_pages()
            else:
                raise RuntimeError(event_data.get("message", "Failed to load agent via CLI."))

        except Exception as e:
            MessageOverlay(f"Error loading agent: {e}", subject="Error")


class AgentLoadButton(LoadButton):

    def __init__(self, master, **kwargs):
        super().__init__(master, command=self._on_click, **kwargs)
        training_state_manager.add_disable_on_train_element(self)

    def _on_click(self):
        FileLoaderOverlaySpawner(
            AGENT_SAVE_FOLDER_PATH,
            "agent",
            _AgentLoaderOverlay,
            exclude_files=[SESSION_STORAGE_KEY],
        )


class AgentAutosaveCheckbox(ctk.CTkCheckBox):
    """When enabled, training writes directly into the bound named agent."""

    def __init__(self, master, **kwargs):
        from loaders import agent_loader

        self._var = ctk.BooleanVar(value=agent_loader.autosave)
        super().__init__(
            master,
            text="Auto-save",
            variable=self._var,
            command=self._on_toggle,
            checkbox_width=20,
            checkbox_height=20,
            font=app_font(size=config.STYLE.FONT.STANDARD_SIZE),
            **kwargs,
        )
        training_state_manager.add_disable_on_train_element(self)
        agent_loader.add_prefs_listener(self._sync_from_loader)

    def _sync_from_loader(self):
        from loaders import agent_loader

        enabled = bool(agent_loader.autosave)
        if bool(self._var.get()) != enabled:
            self._var.set(enabled)

    def _on_toggle(self):
        from loaders import agent_loader
        from app.components.overlay.message_overlay import MessageOverlay

        enabled = bool(self._var.get())
        try:
            agent_loader.set_autosave(enabled)
        except Exception as e:
            self._var.set(agent_loader.autosave)
            MessageOverlay(str(e), subject="Error")
