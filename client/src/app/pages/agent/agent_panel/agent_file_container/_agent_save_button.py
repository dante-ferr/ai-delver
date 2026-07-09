from app.components import SaveButton
from loaders import agent_loader
from agent.config import AGENT_SAVE_FOLDER_PATH


class AgentSaveButton(SaveButton):

    def __init__(self, master):
        super().__init__(master, AGENT_SAVE_FOLDER_PATH, "agent")

    def _save(self):
        import subprocess
        import sys
        import json
        import os
        from config import PROJECT_ROOT
        from app.components.overlay.message_overlay import MessageOverlay

        agent_name = agent_loader.agent.name
        client_dir = os.path.abspath(os.path.join(PROJECT_ROOT, ".."))

        cmd = [
            sys.executable, "src/cli/main.py",
            "save-agent",
            "--name", agent_name
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

            if event_data.get("event") == "agent_saved":
                agent_loader.agent.save()  # sync in-memory representation
                super()._save()
            else:
                raise RuntimeError(event_data.get("message", "Failed to save agent via CLI."))

        except Exception as e:
            MessageOverlay(f"Error saving agent: {e}", subject="Error")

    @property
    def file_name(self) -> str:
        return agent_loader.agent.name
