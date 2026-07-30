import customtkinter as ctk
import sys
from state_managers import training_state_manager
import asyncio
from app.utils import verify_level_issues
from client_requests.gui_training_client import gui_training_client
import threading
from app.components import StandardButton
import subprocess
import os
import json
import time
import signal
from state_managers import trajectory_stats_state_manager
from app.components.overlay.message_overlay import MessageOverlay
from loaders import agent_loader
from bootstrap import PROJECT_ROOT

from app.components import FileLoaderOverlay, SvgImage
from app.theme import theme
from src.config import config
from level.config import LEVEL_SAVE_FOLDER_PATH
from app.components.overlay.file_loader_overlay.file_loader_overlay_spawner import (
    FileLoaderOverlaySpawner,
)


class _QuickPlayLevelOverlay(FileLoaderOverlay):
    def __init__(self, file_dirs, file_type, on_level_selected=None):
        self.on_level_selected = on_level_selected
        super().__init__(
            file_dirs,
            file_type,
            show_sucess_message=False,
        )

    def _prompt_text(self) -> str:
        return "Select a level to quick play."

    def _action_button_text(self) -> str:
        return "Play"

    def _load(self):
        selected_level = self.get_selected_name()
        super()._load()
        if self.on_level_selected:
            self.on_level_selected(selected_level)


class TrainButtonsContainer(ctk.CTkFrame):
    """
    A UI container with two columns of buttons for training and playing/testing levels,
    equipped with responsive icons inside the buttons.
    """

    STACK_BELOW_WIDTH = 340
    DEBOUNCE_MS = 80

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self._stacked: bool | None = None
        self._configure_after_id: str | None = None

        self.train_button = StandardButton(
            self,
            text="Train",
            command=self._start_train_thread,
            svg_path=str(config.ASSETS_PATH / "svg" / "train.svg"),
        )

        self.interrupt_training_button = StandardButton(
            self,
            text="Interrupt Training",
            command=self._start_interrupt_thread,
            svg_path=str(config.ASSETS_PATH / "svg" / "x.svg"),
        )

        self.play_button = StandardButton(
            self,
            text="Play Levels",
            command=self._start_play_thread,
            svg_path=str(config.ASSETS_PATH / "svg" / "test.svg"),
        )

        self.quick_play_button = StandardButton(
            self,
            text="Quick Play Level",
            command=self._open_quick_play_overlay,
            svg_path=str(config.ASSETS_PATH / "svg" / "quick_play.svg"),
        )

        self._apply_button_layout(stacked=False)

        training_state_manager.add_disable_on_train_element(self.train_button)
        training_state_manager.add_disable_on_train_element(self.play_button)
        training_state_manager.add_disable_on_train_element(self.quick_play_button)
        training_state_manager.add_enable_on_train_element(
            self.interrupt_training_button
        )
        self.train_process = None

        self.bind("<Configure>", self._on_configure)

    def _on_configure(self, event):
        if event.widget is not self:
            return
        if self._configure_after_id is not None:
            self.after_cancel(self._configure_after_id)
        self._configure_after_id = self.after(self.DEBOUNCE_MS, self._update_layout)

    def _update_layout(self):
        self._configure_after_id = None
        width = self.winfo_width()
        if width <= 1:
            return
        self._apply_button_layout(stacked=width < self.STACK_BELOW_WIDTH)

    def _apply_button_layout(self, stacked: bool):
        if stacked == self._stacked:
            return
        self._stacked = stacked

        if stacked:
            self.grid_columnconfigure(0, weight=1)
            self.grid_columnconfigure(1, weight=0)
            for row in range(4):
                self.grid_rowconfigure(row, weight=0)

            self.train_button.grid(row=0, column=0, padx=0, pady=(0, 4), sticky="ew")
            self.interrupt_training_button.grid(
                row=1, column=0, padx=0, pady=(0, 8), sticky="ew"
            )
            self.play_button.grid(row=2, column=0, padx=0, pady=(0, 4), sticky="ew")
            self.quick_play_button.grid(
                row=3, column=0, padx=0, pady=0, sticky="ew"
            )
        else:
            self.grid_columnconfigure(0, weight=1)
            self.grid_columnconfigure(1, weight=1)
            for row in range(2):
                self.grid_rowconfigure(row, weight=0)

            # Column 0: Train section (Train, Interrupt Training)
            self.train_button.grid(row=0, column=0, padx=(0, 3), pady=(0, 4), sticky="ew")
            self.interrupt_training_button.grid(
                row=1, column=0, padx=(0, 3), pady=0, sticky="ew"
            )

            # Column 1: Test section (Play Levels, Quick Play Level)
            self.play_button.grid(row=0, column=1, padx=(3, 0), pady=(0, 4), sticky="ew")
            self.quick_play_button.grid(
                row=1, column=1, padx=(3, 0), pady=0, sticky="ew"
            )

    def _start_train_thread(self):
        """
        Starts the training subprocess in a new thread to avoid blocking the GUI.
        """
        if verify_level_issues():
            return

        checkpoint_interval = int(float(training_state_manager.checkpoint_interval))
        if checkpoint_interval < 1:
            MessageOverlay(
                "Checkpoint every N cycles must be at least 1 so training writes mid-run save states.",
                subject="Error",
            )
            return

        thread = threading.Thread(
            target=self._run_subprocess_train, daemon=True
        )
        thread.start()

    def _start_play_thread(self):
        """
        Starts the play subprocess in a new thread to avoid blocking the GUI.
        Puts Delver to play each selected level once, generating and saving trajectories.
        """
        if verify_level_issues():
            return

        if not training_state_manager.training_levels:
            MessageOverlay("No training levels selected.", subject="Error")
            return

        thread = threading.Thread(
            target=self._run_subprocess_play, daemon=True
        )
        thread.start()

    def _open_quick_play_overlay(self):
        FileLoaderOverlaySpawner(
            LEVEL_SAVE_FOLDER_PATH,
            "level",
            overlay_class=lambda dirs, ftype: _QuickPlayLevelOverlay(
                dirs, ftype, on_level_selected=self._start_quick_play_thread
            ),
        )

    def _start_quick_play_thread(self, level_name: str):
        if verify_level_issues():
            return

        thread = threading.Thread(
            target=self._run_quick_play, args=(level_name,), daemon=True
        )
        thread.start()

    def _run_quick_play(self, level_name: str):
        from app_manager import app_manager
        import base64
        from agent.agent import Agent

        training_state_manager.set_value("sending_training_request", True)

        async def _async_quick_play():
            agent_name = agent_loader.storage_key
            gui_training_client.ensure_levels_saved([level_name], agent_name)

            model_bytes_b64 = None
            agent_obj = Agent(agent_name)
            if agent_obj.weights_path and agent_obj.weights_path.is_file():
                with open(agent_obj.weights_path, "rb") as f:
                    model_bytes_b64 = base64.b64encode(f.read()).decode("utf-8")

            payload = gui_training_client.create_training_payload(
                levels=[level_name],
                mode="static",
                amount_of_cycles=1,
                runs_per_cycle=1,
                model_bytes_b64=model_bytes_b64,
                play=True,
            )

            response = await gui_training_client.submit_training(payload)
            session_id = response.get("session_id")
            if not session_id:
                raise RuntimeError("No session_id received from server.")

            gui_training_client.session_id = session_id

            received_trajectory = None

            async def on_trajectory(trajectory, level_episode_count):
                nonlocal received_trajectory
                if trajectory is not None:
                    received_trajectory = trajectory

            def on_level_transition(levels_trained):
                pass

            def on_completed():
                pass

            def on_error(err):
                raise RuntimeError(err)

            await gui_training_client.listen_to_trajectory(
                session_id,
                on_trajectory,
                on_level_transition,
                on_completed,
                on_error,
            )

            return received_trajectory

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            trajectory = loop.run_until_complete(_async_quick_play())
            loop.close()

            if trajectory is None:
                raise RuntimeError("No trajectory received from server.")

            self.after(0, lambda: app_manager.start_replay(trajectory))
        except Exception as e:
            print(f"[Quick Play Error] {e}")
            self.after(
                0,
                lambda err=e: MessageOverlay(
                    f"Quick Play failed: {err}", subject="Error"
                ),
            )
        finally:
            training_state_manager.reset_states()

    def _start_interrupt_thread(self):
        """
        Starts the interrupt request/signal in a new thread to avoid blocking the GUI.
        """
        thread = threading.Thread(
            target=self._interrupt_training, daemon=True
        )
        thread.start()

    def _run_subprocess_play(self):
        training_state_manager.play_session = True
        training_state_manager.set_value("sending_training_request", True)

        levels_str = ",".join(training_state_manager.training_levels)
        mode = "static"
        agent_name = agent_loader.storage_key

        client_dir = os.path.abspath(os.path.join(PROJECT_ROOT, ".."))

        cmd = [
            sys.executable, "src/cli/main.py",
            "train",
            "--levels", levels_str,
            "--mode", mode,
            "--agent", agent_name,
            "--server", gui_training_client.server_url,
            "--play"
        ]

        try:
            self.train_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                cwd=client_dir
            )
            training_state_manager.train_process = self.train_process
        except Exception as e:
            training_state_manager.reset_states()
            print(f"[GUI Error] Failed to start play subprocess: {e}")
            MessageOverlay(f"Failed to start play subprocess: {e}", subject="Error")
            return

        start_time = time.time()

        for line in iter(self.train_process.stdout.readline, ""):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                print(f"[CLI Output] {line}")
                continue

            event = data.get("event")
            if event == "info":
                print(f"[CLI Info] {data.get('message')}")
                continue
            elif event == "error":
                msg = data.get("message", "An unknown error occurred.")
                print(f"[CLI Error] {msg}")
                training_state_manager.remove_review_process_log()
                training_state_manager.reset_states()
                MessageOverlay(msg, subject="Error")
                continue
            elif event == "init_started" or event == "request_sent" or event == "interrupt_started":
                if event == "interrupt_started":
                    training_state_manager.set_value("sending_interrupt_training_request", True)
                else:
                    training_state_manager.set_value("sending_training_request", True)
            elif event == "session_created":
                training_state_manager.set_value("sending_training_request", False)
                training_state_manager.set_value("training", True)
                gui_training_client.session_id = data.get("session_id")
            elif event == "progress":
                cycle = data.get("cycle", 0)
                level_episode_count = data.get("level_episode_count", 0)
                training_state_manager.set_value("level_episode_count", level_episode_count)
                training_state_manager.update_training_process_log(cycle)
                # Review showcases are not persisted; only refresh the list for saved ones.
                if data.get("persisted", True) and not data.get("is_review", False):
                    trajectory_stats_state_manager.notify_trajectory_added()
                    agent_loader.mark_dirty()
            elif event == "showcase":
                if data.get("persisted", True) and not data.get("is_review", False):
                    trajectory_stats_state_manager.notify_trajectory_added()
                    agent_loader.mark_dirty()
            elif event == "level_transition":
                levels_trained = data.get("levels_trained", 0)
                training_state_manager.set_value("levels_trained", levels_trained)
            elif event == "completed":
                duration = time.time() - start_time
                minutes, seconds = divmod(duration, 60)
                time_str = f"{int(minutes)}m {int(seconds)}s" if minutes > 0 else f"{seconds:.2f}s"
                # Fill the play progress bar to completion before tearing it down.
                training_state_manager.update_training_process_log(
                    len(training_state_manager.training_levels)
                )
                training_state_manager.reset_states()
                trajectory_stats_state_manager.refresh_stats()
                agent_loader.mark_dirty()
                MessageOverlay(f"Play session completed in {time_str}.", subject="Success")
            elif event == "interrupted":
                training_state_manager.reset_states()
                trajectory_stats_state_manager.refresh_stats()
                agent_loader.mark_dirty()
                MessageOverlay("Play session interrupted.", subject="Success")

        self.train_process.wait()
        if training_state_manager.train_process is self.train_process:
            training_state_manager.train_process = None

        if training_state_manager.get_value("training") or training_state_manager.get_value("sending_training_request"):
            stderr_out = self.train_process.stderr.read().strip()
            err_msg = f"\nStderr: {stderr_out}" if stderr_out else ""
            training_state_manager.reset_states()
            print(f"[GUI Error] Play process exited with code {self.train_process.returncode}.{err_msg}")
            MessageOverlay(f"Play process exited with code {self.train_process.returncode}.{err_msg}", subject="Error")

    def _run_subprocess_train(self):
        # Clear state/set sending
        training_state_manager.play_session = False
        training_state_manager.set_value("sending_training_request", True)
        training_state_manager.clear_nerd_metrics()

        # Build command args
        levels_str = ",".join(training_state_manager.training_levels)
        cycles = str(int(float(training_state_manager.amount_of_cycles)))
        runs_per_cycle = str(int(float(training_state_manager.runs_per_cycle)))
        checkpoint_interval = str(int(float(training_state_manager.checkpoint_interval)))
        mode = "static"
        agent_name = agent_loader.storage_key

        client_dir = os.path.abspath(os.path.join(PROJECT_ROOT, ".."))

        cmd = [
            sys.executable, "src/cli/main.py",
            "train",
            "--levels", levels_str,
            "--cycles", cycles,
            "--runs-per-cycle", runs_per_cycle,
            "--checkpoint-interval", checkpoint_interval,
            "--mode", mode,
            "--agent", agent_name,
            "--server", gui_training_client.server_url
        ]
        if training_state_manager.early_stop:
            cmd.append("--early-stop")

        try:
            self.train_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                cwd=client_dir
            )
            training_state_manager.train_process = self.train_process
        except Exception as e:
            training_state_manager.reset_states()
            print(f"[GUI Error] Failed to start training subprocess: {e}")
            MessageOverlay(f"Failed to start training subprocess: {e}", subject="Error")
            return

        start_time = time.time()

        # Read stdout line by line
        for line in iter(self.train_process.stdout.readline, ""):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                # If it's not JSON, print it to standard stdout
                print(f"[CLI Output] {line}")
                continue

            event = data.get("event")
            if event == "info":
                print(f"[CLI Info] {data.get('message')}")
                continue
            elif event == "error":
                msg = data.get("message", "An unknown error occurred.")
                print(f"[CLI Error] {msg}")
                training_state_manager.remove_review_process_log()
                training_state_manager.reset_states()
                MessageOverlay(msg, subject="Error")
                continue
            elif event == "init_started" or event == "request_sent" or event == "interrupt_started":
                if event == "interrupt_started":
                    training_state_manager.set_value("sending_interrupt_training_request", True)
                else:
                    training_state_manager.set_value("sending_training_request", True)
            elif event == "session_created":
                training_state_manager.set_value("sending_training_request", False)
                training_state_manager.set_value("training", True)
                gui_training_client.session_id = data.get("session_id")
            elif event == "training_phase":
                phase = data.get("phase")
                expected = int(data.get("expected_progress_steps") or 0)
                progress_base = int(data.get("progress_base") or 0)
                print(f"[CLI Info] Training phase: {phase}")
                if phase == "focus":
                    # Review bar is only for the review phase; hide it when focus resumes
                    # or when the chain continues after a review commit.
                    training_state_manager.remove_review_process_log()
                if expected > 0:
                    if phase == "review":
                        training_state_manager.show_review_process_log(expected)
                    elif phase == "focus":
                        training_state_manager.set_training_process_log_total(
                            expected, progress_base=progress_base
                        )
            elif event == "review_plan":
                print(f"[CLI Info] {data.get('message')}")
            elif event == "progress":
                cycle = data.get("cycle", 0)
                level_episode_count = data.get("level_episode_count", 0)
                training_state_manager.set_value("level_episode_count", level_episode_count)
                phase = data.get("training_phase") or (
                    "review" if data.get("is_review") else "focus"
                )
                if phase == "review":
                    training_state_manager.update_review_process_log(cycle)
                else:
                    training_state_manager.update_training_process_log(cycle)
                # Review showcases are not persisted; only refresh the list for saved ones.
                if data.get("persisted", True) and not data.get("is_review", False):
                    trajectory_stats_state_manager.notify_trajectory_added()
                    agent_loader.mark_dirty()
            elif event == "level_transition":
                levels_trained = data.get("levels_trained", 0)
                training_state_manager.set_value("levels_trained", levels_trained)
            elif event == "metrics":
                step = data.get("step")
                loss = data.get("loss")
                average_return = data.get("average_return")
                episodes = data.get("episodes")
                training_state_manager.update_nerd_metrics(step, loss, average_return, episodes)
            elif event == "completed":
                duration = time.time() - start_time
                minutes, seconds = divmod(duration, 60)
                time_str = f"{int(minutes)}m {int(seconds)}s" if minutes > 0 else f"{seconds:.2f}s"
                # Drop review bar before reset in case the session ended on a review phase.
                training_state_manager.remove_review_process_log()
                training_state_manager.reset_states()
                agent_loader.mark_dirty()
                trajectory_stats_state_manager.refresh_stats()
                MessageOverlay(f"Training session completed in {time_str}.", subject="Success")
            elif event == "interrupted":
                training_state_manager.remove_review_process_log()
                training_state_manager.reset_states()
                agent_loader.mark_dirty()
                trajectory_stats_state_manager.refresh_stats()
                MessageOverlay("Training session interrupted.", subject="Success")

        # Wait for process to exit
        self.train_process.wait()
        if training_state_manager.train_process is self.train_process:
            training_state_manager.train_process = None

        # In case it exited without sending completed/interrupted events (e.g. crash)
        if training_state_manager.get_value("training") or training_state_manager.get_value("sending_training_request"):
            stderr_out = self.train_process.stderr.read().strip()
            err_msg = f"\nStderr: {stderr_out}" if stderr_out else ""
            training_state_manager.reset_states()
            print(f"[GUI Error] Training process exited with code {self.train_process.returncode}.{err_msg}")
            MessageOverlay(f"Training process exited with code {self.train_process.returncode}.{err_msg}", subject="Error")

    def _interrupt_training(self):
        training_state_manager.set_value("sending_interrupt_training_request", True)
        if self.train_process and self.train_process.poll() is None:
            try:
                self.train_process.send_signal(signal.SIGINT)
            except Exception as e:
                print(f"Failed to send SIGINT to subprocess: {e}")
                self._run_cli_interrupt()
        else:
            self._run_cli_interrupt()

    def _run_cli_interrupt(self):
        client_dir = os.path.abspath(os.path.join(PROJECT_ROOT, ".."))
        cmd = [
            sys.executable, "src/cli/main.py",
            "interrupt",
            "--session-id", str(gui_training_client.session_id),
            "--server", gui_training_client.server_url
        ]
        try:
            subprocess.run(cmd, cwd=client_dir)
        except Exception as e:
            print(f"Failed to run CLI interrupt: {e}")
