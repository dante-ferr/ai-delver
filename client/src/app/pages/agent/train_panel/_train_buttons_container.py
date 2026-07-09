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


class TrainButtonsContainer(ctk.CTkFrame):
    """
    A UI container with buttons to start and interrupt agent training.
    It runs the CLI training client script as a subprocess in a separate thread.
    """

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.train_button = StandardButton(
            self, text="Train", command=self._start_train_thread
        )
        self.train_button.grid(row=0, column=0, padx=(0, 4))

        self.interrupt_training_button = StandardButton(
            self,
            text="Interrupt Training",
            command=self._start_interrupt_thread,
        )
        self.interrupt_training_button.grid(row=0, column=1, padx=(4, 0))

        training_state_manager.add_disable_on_train_element(self.train_button)
        training_state_manager.add_enable_on_train_element(
            self.interrupt_training_button
        )
        self.train_process = None

    def _start_train_thread(self):
        """
        Starts the training subprocess in a new thread to avoid blocking the GUI.
        """
        if verify_level_issues():
            return
            
        thread = threading.Thread(
            target=self._run_subprocess_train, daemon=True
        )
        thread.start()

    def _start_interrupt_thread(self):
        """
        Starts the interrupt request/signal in a new thread to avoid blocking the GUI.
        """
        thread = threading.Thread(
            target=self._interrupt_training, daemon=True
        )
        thread.start()

    def _run_subprocess_train(self):
        # Clear state/set sending
        training_state_manager.set_value("sending_training_request", True)
        training_state_manager.clear_nerd_metrics()
        
        # Build command args
        levels_str = ",".join(training_state_manager.training_levels)
        cycles = str(int(float(training_state_manager.amount_of_cycles)))
        episodes_per_cycle = str(int(float(training_state_manager.episodes_per_cycle)))
        mode = training_state_manager.get_value("level_transitioning_mode")
        agent_name = agent_loader.agent.name
        
        client_dir = os.path.abspath(os.path.join(PROJECT_ROOT, ".."))

        cmd = [
            sys.executable, "src/cli/main.py",
            "train",
            "--levels", levels_str,
            "--cycles", cycles,
            "--episodes-per-cycle", episodes_per_cycle,
            "--mode", mode,
            "--agent", agent_name,
            "--server", gui_training_client.server_url
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
                trajectory_stats_state_manager.notify_trajectory_added()
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
                training_state_manager.reset_states()
                trajectory_stats_state_manager.refresh_stats()
                MessageOverlay(f"Training session completed in {time_str}.", subject="Success")
            elif event == "interrupted":
                training_state_manager.reset_states()
                trajectory_stats_state_manager.refresh_stats()
                MessageOverlay("Training session interrupted.", subject="Success")

                
        # Wait for process to exit
        self.train_process.wait()
        
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

