import customtkinter as ctk
import sys
import threading
import subprocess
import json
import os
from state_managers import trajectory_stats_state_manager, training_state_manager
from src.app.components import LoadingLogsPanel, SectionTitle
from loaders import agent_loader
from app.components import StandardButton
from app.fonts import app_font
from src.config import config
from bootstrap import PROJECT_ROOT

from ._all_stats_window import AllStatsWindow


class TrajectoryStatsPanel(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent", width=0, height=0)

        title = SectionTitle(self, text="Trajectory Stats")
        title.pack(pady=(0, 8), side="top", anchor="w")

        fetch_container = ctk.CTkFrame(self, fg_color="transparent", width=0, height=0)
        fetch_container.pack(fill="x", pady=(0, 8))

        fetch_container.columnconfigure(0, weight=1)

        stats_logs_panel = LoadingLogsPanel(
            fetch_container, width=180, fg_color="transparent"
        )
        stats_logs_panel.pack_propagate(False)
        stats_logs_panel.grid(row=0, column=0, sticky="w")

        trajectory_stats_state_manager.set_stats_logs_panel(stats_logs_panel)

        self.stats_container = ctk.CTkFrame(
            self, fg_color="transparent", width=0, height=0
        )
        self.stats_container.pack(fill="x")

        self.all_stats_button = StandardButton(
            self,
            text="All Stats",
            command=self._open_all_stats,
            svg_path=str(config.ASSETS_PATH / "svg" / "stats.svg"),
            font=app_font(size=11, weight="bold"),
        )
        self.all_stats_button.pack(fill="x", pady=(8, 0))

        self.level_archive_button = StandardButton(
            self,
            text="Level Archive",
            command=self._open_level_archive,
            svg_path=str(config.ASSETS_PATH / "svg" / "archive.svg"),
            font=app_font(size=11, weight="bold"),
        )
        self.level_archive_button.pack(fill="x", pady=(4, 0))

        # Register callbacks to refresh stats automatically
        trajectory_stats_state_manager.add_on_refresh_stats_callback(
            self._start_stats_job
        )
        trajectory_stats_state_manager.add_on_trajectory_added_callback(
            self._start_stats_job
        )

        self._start_stats_job()

    def _start_stats_job(self):
        """
        Starts a background thread to run the CLI stats command and update the UI.
        """
        trajectory_stats_state_manager.getting_stats = True

        wait_thread = threading.Thread(
            target=self._run_stats_subprocess, daemon=True
        )
        wait_thread.start()

    def _run_stats_subprocess(self):
        """Executes the CLI stats command and updates the UI with the output."""
        agent_name = agent_loader.storage_key
        client_dir = os.path.abspath(os.path.join(PROJECT_ROOT, ".."))

        cmd = [
            sys.executable, "src/cli/main.py",
            "stats",
            "--agent", agent_name
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

            stats_result = None
            nerd_stats_result = None
            for line in stdout_out.splitlines():
                line = line.strip()
                if line.startswith("{"):
                    try:
                        data = json.loads(line)
                        if data.get("event") == "stats":
                            stats_result = data.get("stats")
                            nerd_stats_result = data.get("nerd_stats", {})
                            break
                    except json.JSONDecodeError:
                        continue

            if stats_result is None:
                raise ValueError("No stats output found in CLI response.")

            # Populate nerd stats state from the CLI response (protocol-compliant)
            if nerd_stats_result:
                training_state_manager.all_time_loss_history = nerd_stats_result.get("loss_history", []) or []
                training_state_manager.all_time_return_history = nerd_stats_result.get("return_history", []) or []
                training_state_manager.all_time_step_history = nerd_stats_result.get("step_history", []) or []

                # Restore latest session from disk when not actively training.
                # Prefer disk when it has at least as much data as memory so a
                # just-saved session wins; keep longer in-memory data if save
                # is still in flight (e.g. interrupt race).
                is_training = (
                    training_state_manager.get_value("training")
                    or training_state_manager.get_value("sending_training_request")
                )
                if not is_training:
                    latest = nerd_stats_result.get("latest_session") or {}
                    latest_loss = list(latest.get("loss_history", []) or [])
                    if len(latest_loss) >= len(training_state_manager.nerd_loss_history):
                        training_state_manager.nerd_loss_history = latest_loss
                        training_state_manager.nerd_return_history = list(
                            latest.get("return_history", []) or []
                        )
                        training_state_manager.nerd_step_history = list(
                            latest.get("step_history", []) or []
                        )

            self.after(0, self._update_ui, stats_result)

        except Exception as e:
            print(f"An error occurred in the stats CLI calculation: {e}")
            self.after(0, self._update_ui, {"error": str(e)})

    def _update_ui(self, stats: dict):
        """
        This function is executed by the main thread via `self.after()`.
        It's the only place where we safely modify the UI.
        """
        try:
            # Clear previous stats
            for widget in self.stats_container.winfo_children():
                widget.destroy()

            if "error" in stats:
                label = ctk.CTkLabel(
                    self.stats_container,
                    text=f"Error: {stats['error']}",
                    text_color="red",
                    font=app_font(size=config.STYLE.FONT.STANDARD_SIZE),
                )
                label.pack(anchor="w", padx=4, pady=0)
                trajectory_stats_state_manager.victories_history = []
                trajectory_stats_state_manager.steps_history = []
            elif stats:
                for stat_name, stat_value in stats.items():
                    # Avoid showing raw list histories as simple text labels
                    if isinstance(stat_value, (list, dict)):
                        continue
                    display_name = stat_name.replace("_", " ").capitalize()
                    pady_val = (0, 8) if stat_name == "processed_count" else (0, 0)
                    label = ctk.CTkLabel(
                        self.stats_container,
                        text=f"{display_name}: {stat_value}",
                        font=app_font(size=config.STYLE.FONT.STANDARD_SIZE),
                    )
                    label.pack(anchor="w", padx=4, pady=pady_val)

                trajectory_stats_state_manager.victories_history = list(
                    stats.get("victories_history", []) or []
                )
                trajectory_stats_state_manager.steps_history = list(
                    stats.get("steps_history", []) or []
                )
            else:
                label = ctk.CTkLabel(
                    self.stats_container,
                    text="No stats found.",
                    font=app_font(size=config.STYLE.FONT.STANDARD_SIZE),
                )
                label.pack(anchor="w", padx=4, pady=0)
                trajectory_stats_state_manager.victories_history = []
                trajectory_stats_state_manager.steps_history = []

            trajectory_stats_state_manager.notify_stats_updated()

        finally:
            # Ensure the loading state is always reset.
            trajectory_stats_state_manager.getting_stats = False

    def _open_all_stats(self):
        """Opens the All Stats window, reusing an existing one if still open."""
        if hasattr(self, "_all_stats_win") and self._all_stats_win.winfo_exists():
            self._all_stats_win.lift()
            self._all_stats_win.focus_set()
            return
        self._all_stats_win = AllStatsWindow(self)

    def _open_level_archive(self):
        """Opens the Level Archive window, reusing an existing one if still open."""
        if hasattr(self, "_level_archive_win") and self._level_archive_win.winfo_exists():
            self._level_archive_win.lift()
            self._level_archive_win.focus_set()
            return
        from ..level_archive_window import LevelArchiveWindow

        self._level_archive_win = LevelArchiveWindow(self)
