import customtkinter as ctk

from app.components import StandardButton
from app.fonts import app_font
from app.components.overlay.message_overlay import MessageOverlay
from state_managers import training_state_manager
from src.config import config


class AgentNewSessionButton(StandardButton):
    """Wipe ``__session__`` and start a blank unbound Delver."""

    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            text="New Delver",
            command=self._on_click,
            font=app_font(size=config.STYLE.FONT.STANDARD_SIZE),
            width=96,
            **kwargs,
        )
        training_state_manager.add_disable_on_train_element(self)

    def _on_click(self):
        MessageOverlay(
            "Start a new blank Delver session? Unsaved session trajectories "
            "and weights will be lost. Named agents on disk are not deleted.",
            subject="Warning",
            button_commands={
                "Create": self._create_new,
                "Cancel": lambda: None,
            },
        )

    def _create_new(self):
        import subprocess
        import sys
        import json
        import os
        from bootstrap import PROJECT_ROOT
        from app_manager import app_manager
        from loaders import agent_loader
        from state_managers import training_state_manager

        client_dir = os.path.abspath(os.path.join(PROJECT_ROOT, ".."))
        cmd = [sys.executable, "src/cli/main.py", "reset-agent-session"]

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=client_dir,
            )
            stdout_out, stderr_out = process.communicate()

            if process.returncode != 0:
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
                raise RuntimeError(
                    error_message or f"Subprocess exited with code {process.returncode}"
                )

            event_data = {}
            for line in stdout_out.splitlines():
                if line.strip().startswith("{"):
                    try:
                        event_data = json.loads(line)
                        break
                    except json.JSONDecodeError:
                        continue

            if event_data.get("event") != "agent_session_reset":
                raise RuntimeError(
                    event_data.get("message", "Failed to reset agent session via CLI.")
                )

            agent_loader._create_new_agent()
            training_state_manager.clear_nerd_metrics()
            training_state_manager.all_time_loss_history = []
            training_state_manager.all_time_return_history = []
            training_state_manager.all_time_step_history = []
            app_manager.editor_app.restart_all_pages()
            MessageOverlay(
                event_data.get("message", "Started a new Delver session."),
                subject="Success",
            )
        except Exception as e:
            MessageOverlay(f"Error creating new Delver: {e}", subject="Error")
