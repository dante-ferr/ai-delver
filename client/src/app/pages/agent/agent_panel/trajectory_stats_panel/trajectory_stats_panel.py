from runtime.episode_trajectory import TrajectoryStatsCalculator
import customtkinter as ctk
import asyncio
import threading
from concurrent.futures import ProcessPoolExecutor
from state_managers import trajectory_stats_state_manager
from src.app.components import LoadingLogsPanel, SectionTitle
from loaders import agent_loader
from app.components import StandardButton
from src.config import config


def run_async_stats_in_process(agent_name: str) -> dict:
    """
    This function is executed in a separate process. It's responsible for
    creating a new asyncio event loop and running the required async task.
    """
    stats_calculator = TrajectoryStatsCalculator(agent_name)
    return asyncio.run(stats_calculator.get_stats())


class TrajectoryStatsPanel(ctk.CTkFrame):
    executor = ProcessPoolExecutor(max_workers=2)

    def __init__(self, master):
        super().__init__(master, fg_color="transparent", width=0, height=0)

        title = SectionTitle(self, text="Trajectory Stats")
        title.pack(pady=(0, 8), side="top", anchor="w")

        fetch_container = ctk.CTkFrame(self, fg_color="transparent", width=0, height=0)
        fetch_container.pack(fill="x", pady=(0, 8))

        fetch_container.columnconfigure(0, weight=0)
        fetch_container.columnconfigure(1, weight=0)

        get_stats_button = StandardButton(
            fetch_container, text="Get stats", command=self._start_stats_job
        )
        get_stats_button.grid(row=0, column=0, padx=(0, 8), pady=0, sticky="n")
        trajectory_stats_state_manager.add_disable_on_get_stats_element(
            get_stats_button
        )

        stats_logs_panel = LoadingLogsPanel(
            fetch_container, width=64, fg_color="transparent"
        )
        stats_logs_panel.pack_propagate(False)
        stats_logs_panel.grid(row=0, column=1, padx=(8, 0), sticky="ns")

        trajectory_stats_state_manager.set_stats_logs_panel(stats_logs_panel)

        self.stats_container = ctk.CTkFrame(
            self, fg_color="transparent", width=0, height=0
        )
        self.stats_container.pack(fill="x")

        trajectory_stats_state_manager.add_on_refresh_stats_callback(
            self._start_stats_job
        )
        self._start_stats_job()

    def _start_stats_job(self):
        """
        Submits the CPU-bound async task to the process pool and starts a
        thread to wait for the result without blocking the UI.
        """
        trajectory_stats_state_manager.getting_stats = True

        future = self.executor.submit(
            run_async_stats_in_process, agent_loader.agent.name
        )

        wait_thread = threading.Thread(
            target=self._await_future_result, args=(future,), daemon=True
        )
        wait_thread.start()

    def _await_future_result(self, future):
        """
        Runs in a background thread, waits for the result from the
        separate process, and then schedules the UI update on the main thread.
        """
        try:
            stats_result = future.result()

            self.after(0, self._update_ui, stats_result)
        except Exception as e:
            print(f"An error occurred in the stats calculation process: {e}")

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
                    font=ctk.CTkFont(size=config.STYLE.FONT.STANDARD_SIZE),
                )
                label.pack(anchor="w", padx=4, pady=2)
            elif stats:
                for stat_name, stat_value in stats.items():
                    label = ctk.CTkLabel(
                        self.stats_container,
                        text=f"{stat_name.capitalize()}: {stat_value}",
                        font=ctk.CTkFont(size=config.STYLE.FONT.STANDARD_SIZE),
                    )
                    label.pack(anchor="w", padx=4, pady=2)
            else:
                label = ctk.CTkLabel(
                    self.stats_container,
                    text="No stats found.",
                    font=ctk.CTkFont(size=config.STYLE.FONT.STANDARD_SIZE),
                )
                label.pack(anchor="w", padx=4, pady=2)

        finally:
            # Ensure the loading state is always reset.
            trajectory_stats_state_manager.getting_stats = False
