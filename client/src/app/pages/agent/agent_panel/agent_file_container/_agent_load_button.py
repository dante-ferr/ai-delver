from app.components import FileLoaderOverlay, LoadButton
from agent.config import AGENT_SAVE_FOLDER_PATH
from app.components.overlay.file_loader_overlay.file_loader_overlay_spawner import (
    FileLoaderOverlaySpawner,
)


class _AgentLoaderOverlay(FileLoaderOverlay):
    def _load(self):
        import subprocess
        import sys
        import json
        import os
        from loaders import agent_loader
        from app_manager import app_manager
        from config import PROJECT_ROOT
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
                app_manager.editor_app.restart_all_pages()
            else:
                raise RuntimeError(event_data.get("message", "Failed to load agent via CLI."))

        except Exception as e:
            MessageOverlay(f"Error loading agent: {e}", subject="Error")


class AgentLoadButton(LoadButton):

    def __init__(self, master, **kwargs):
        super().__init__(master, command=self._on_click, **kwargs)

    def _on_click(self):
        FileLoaderOverlaySpawner(AGENT_SAVE_FOLDER_PATH, "agent", _AgentLoaderOverlay)
