from pathlib import Path
from app.components import SaveButton
from loaders import agent_loader
from agent.config import AGENT_SAVE_FOLDER_PATH
from state_managers import training_state_manager


class AgentSaveButton(SaveButton):

    def __init__(self, master):
        super().__init__(master, AGENT_SAVE_FOLDER_PATH, "agent")
        training_state_manager.add_disable_on_train_element(self)

    def _save(self):
        import subprocess
        import sys
        import json
        import os
        from bootstrap import PROJECT_ROOT
        from app.components.overlay.message_overlay import MessageOverlay

        agent_name = agent_loader.agent.name.strip()
        source_name = agent_loader.persisted_name
        renamed = bool(source_name) and source_name != agent_name
        dest_exists = (Path(AGENT_SAVE_FOLDER_PATH) / agent_name).is_dir()
        client_dir = os.path.abspath(os.path.join(PROJECT_ROOT, ".."))

        cmd = [
            sys.executable, "src/cli/main.py",
            "save-agent",
            "--name", agent_name,
        ]
        if source_name:
            cmd.extend(["--from", source_name])
        if renamed and dest_exists:
            cmd.append("--force")

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
                # Prefer JSON error events from the CLI when present.
                error_message = stderr_out.strip()
                for line in stdout_out.splitlines():
                    if line.strip().startswith("{"):
                        try:
                            payload = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if payload.get("event") == "error":
                            error_message = payload.get("message") or error_message
                            break
                raise RuntimeError(error_message or f"Subprocess exited with code {process.returncode}")

            event_data = {}
            for line in stdout_out.splitlines():
                if line.strip().startswith("{"):
                    try:
                        event_data = json.loads(line)
                        break
                    except json.JSONDecodeError:
                        continue

            if event_data.get("event") == "agent_saved":
                agent_loader.load_agent(Path(AGENT_SAVE_FOLDER_PATH) / agent_name)
                super()._save()
                if renamed:
                    from app_manager import app_manager
                    app_manager.editor_app.restart_all_pages()
            else:
                raise RuntimeError(event_data.get("message", "Failed to save agent via CLI."))

        except Exception as e:
            MessageOverlay(f"Error saving agent: {e}", subject="Error")

    @property
    def file_name(self) -> str:
        return agent_loader.agent.name
