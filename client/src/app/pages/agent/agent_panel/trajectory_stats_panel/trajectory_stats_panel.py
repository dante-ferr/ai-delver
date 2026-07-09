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


class StatsMiniGraph(ctk.CTkCanvas):
    """
    A custom, high-performance canvas-based mini graph to plot trajectory
    metrics (like victories or step counts) inline without using matplotlib.
    """
    def __init__(self, master, title: str, line_color: str, **kwargs):
        bg_color = master.cget("fg_color")
        if not bg_color or bg_color == "transparent":
            bg_color = "#2b2b2b"

        super().__init__(
            master,
            bg=bg_color,
            highlightthickness=0,
            **kwargs
        )
        self.title = title
        self.line_color = line_color
        self.data = []
        self.bind("<Configure>", lambda e: self.redraw())

    def set_data(self, data: list):
        self.data = data
        self.redraw()

    def redraw(self):
        self.delete("all")

        width = self.winfo_width()
        height = self.winfo_height()

        if width <= 1 or height <= 1:
            return

        # Margins
        margin_left = 35
        margin_right = 10
        margin_top = 22
        margin_bottom = 20

        plot_w = width - margin_left - margin_right
        plot_h = height - margin_top - margin_bottom

        # Draw title
        self.create_text(
            width / 2, 8,
            text=self.title,
            fill="#ffffff",
            font=("Arial", 9, "bold")
        )

        # Draw axes
        self.create_line(
            margin_left, margin_top,
            margin_left, height - margin_bottom,
            fill="#555555", width=1
        )
        self.create_line(
            margin_left, height - margin_bottom,
            width - margin_right, height - margin_bottom,
            fill="#555555", width=1
        )

        if not self.data:
            self.create_text(
                width / 2, height / 2,
                text="No data",
                fill="#888888",
                font=("Arial", 9)
            )
            return

        n = len(self.data)
        max_val = max(self.data)
        min_val = min(self.data)

        # Avoid division by zero
        val_range = max_val - min_val
        if val_range == 0:
            val_range = 1
            min_val = max(0.0, min_val - 0.5)

        # Draw grid & Y labels (min, middle, max)
        for i in range(3):
            ratio = i / 2.0
            y = height - margin_bottom - ratio * plot_h
            val = min_val + ratio * (max_val - min_val)

            # Grid line
            self.create_line(
                margin_left, y,
                width - margin_right, y,
                fill="#3a3a3a", dash=(2, 2)
            )

            # Label
            val_str = f"{int(val)}" if val.is_integer() else f"{val:.1f}"
            if val > 1000:
                val_str = f"{val/1000:.1f}k"
            self.create_text(
                margin_left - 5, y,
                text=val_str,
                anchor="e",
                fill="#aaaaaa",
                font=("Arial", 7)
            )

        # Draw X labels (first and last index)
        self.create_text(
            margin_left, height - margin_bottom + 4,
            text="1",
            anchor="n",
            fill="#aaaaaa",
            font=("Arial", 7)
        )
        self.create_text(
            width - margin_right, height - margin_bottom + 4,
            text=str(n),
            anchor="n",
            fill="#aaaaaa",
            font=("Arial", 7)
        )

        # Draw data line
        points = []
        for idx, val in enumerate(self.data):
            x = margin_left + (idx / max(1, n - 1)) * plot_w
            y = height - margin_bottom - ((val - min_val) / val_range) * plot_h
            points.append((x, y))

        # Draw lines connecting points
        for idx in range(len(points) - 1):
            p1 = points[idx]
            p2 = points[idx+1]
            self.create_line(
                p1[0], p1[1],
                p2[0], p2[1],
                fill=self.line_color,
                width=2
            )


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

        # Inline custom charts
        self.graphs_container = ctk.CTkFrame(self, fg_color="transparent")
        self.graphs_container.pack(fill="x", pady=(8, 0))

        self.victories_graph = StatsMiniGraph(
            self.graphs_container,
            title="Accumulated Victories",
            line_color="#10b981", # Emerald Green
            height=100
        )
        self.victories_graph.pack(fill="x", pady=(0, 8))

        self.steps_graph = StatsMiniGraph(
            self.graphs_container,
            title="Trajectory Steps",
            line_color="#8b5cf6", # Violet
            height=100
        )
        self.steps_graph.pack(fill="x", pady=0)

        # Nerd stats button
        self.nerd_stats_button = StandardButton(
            self,
            text="Nerd Stats",
            command=self._open_nerd_stats,
            width=120
        )
        self.nerd_stats_button.pack(anchor="w", pady=(12, 0))

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
                # Reset graphs
                self.victories_graph.set_data([])
                self.steps_graph.set_data([])
            elif stats:
                for stat_name, stat_value in stats.items():
                    # Avoid showing raw list histories as simple text labels
                    if isinstance(stat_value, (list, dict)):
                        continue
                    label = ctk.CTkLabel(
                        self.stats_container,
                        text=f"{stat_name.capitalize()}: {stat_value}",
                        font=ctk.CTkFont(size=config.STYLE.FONT.STANDARD_SIZE),
                    )
                    label.pack(anchor="w", padx=4, pady=2)

                # Update data on custom graphs
                self.victories_graph.set_data(stats.get("victories_history", []))
                self.steps_graph.set_data(stats.get("steps_history", []))
            else:
                label = ctk.CTkLabel(
                    self.stats_container,
                    text="No stats found.",
                    font=ctk.CTkFont(size=config.STYLE.FONT.STANDARD_SIZE),
                )
                label.pack(anchor="w", padx=4, pady=2)
                # Reset graphs
                self.victories_graph.set_data([])
                self.steps_graph.set_data([])

        finally:
            # Ensure the loading state is always reset.
            trajectory_stats_state_manager.getting_stats = False

    def _open_nerd_stats(self):
        """Opens a Toplevel window showing Nerd Stats placeholders."""
        nerd_win = ctk.CTkToplevel(self)
        nerd_win.title("Dojo Nerd Stats")
        nerd_win.geometry("600x400")

        nerd_win.lift()
        nerd_win.focus_set()

        label = ctk.CTkLabel(
            nerd_win,
            text="Training Nerd Stats (Deep Learning Metrics)",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        label.pack(pady=16, padx=16, anchor="w")

        placeholder = ctk.CTkLabel(
            nerd_win,
            text="This panel will contain detailed deep learning-related training stats\nsent by the server (e.g. loss, learning rate, and average returns) plotted in detail.\n\n(Nerd stats design in discussion)",
            font=ctk.CTkFont(size=config.STYLE.FONT.STANDARD_SIZE),
            justify="left"
        )
        placeholder.pack(pady=20, padx=16, anchor="w")
