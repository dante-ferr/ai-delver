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
from src.config import config
from bootstrap import PROJECT_ROOT


class StatsMiniGraph(ctk.CTkCanvas):
    """
    A custom, high-performance canvas-based mini graph to plot trajectory
    metrics (like victories or step counts) inline without using matplotlib.
    """
    def __init__(self, master, title: str, line_color: str, empty_text: str = "No data", **kwargs):
        # Resolve a real single Tk color for the canvas bg.
        # CTk's fg_color can be:
        #   - A (light, dark) tuple
        #   - A space-separated "light dark" string (Toplevel/App quirk)
        #   - "transparent" (must walk up to find a real color)
        #   - A plain hex string
        bg_color = self._resolve_bg_color(master)

        super().__init__(
            master,
            bg=bg_color,
            highlightthickness=0,
            **kwargs
        )
        self.title = title
        self.line_color = line_color
        self.empty_text = empty_text
        self.data = []
        self.bind("<Configure>", lambda e: self.redraw())

    @staticmethod
    def _resolve_bg_color(widget, fallback: str = "#2b2b2b") -> str:
        """
        Walks up the widget tree to resolve a real Tk-compatible background color.
        Handles CTk's internal (light, dark) tuple, space-separated strings, and
        'transparent' by climbing to the nearest ancestor with a concrete color.
        """
        mode_index = 0 if ctk.get_appearance_mode() == "Light" else 1

        current = widget
        while current is not None:
            try:
                raw = current.cget("fg_color")
            except Exception:
                break

            # Tuple form: ("light_color", "dark_color")
            if isinstance(raw, (list, tuple)) and len(raw) == 2:
                color = raw[mode_index]
            elif isinstance(raw, str) and " " in raw:
                parts = raw.split()
                color = parts[min(mode_index, len(parts) - 1)]
            else:
                color = raw

            if color and color != "transparent":
                return color

            # Climb one level
            try:
                current = current.master
            except AttributeError:
                break

        return fallback


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
                text=self.empty_text,
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
        Starts a background thread to run the CLI stats command and update the UI.
        """
        trajectory_stats_state_manager.getting_stats = True

        wait_thread = threading.Thread(
            target=self._run_stats_subprocess, daemon=True
        )
        wait_thread.start()

    def _run_stats_subprocess(self):
        """Executes the CLI stats command and updates the UI with the output."""
        agent_name = agent_loader.agent.name
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
        """Opens the Nerd Stats window, reusing an existing one if still open."""
        if hasattr(self, "_nerd_win") and self._nerd_win.winfo_exists():
            self._nerd_win.lift()
            self._nerd_win.focus_set()
            return
        self._nerd_win = NerdStatsWindow(self)


class NerdStatsWindow(ctk.CTkToplevel):
    """
    A Toplevel window that displays real-time deep learning training metrics
    (Loss and Average Return) as mini line charts, updated live during training.
    """

    def __init__(self, master):
        super().__init__(master)
        self.title("Dojo Nerd Stats")
        self.geometry("900x550")
        self.resizable(True, True)
        self.lift()
        self.focus_set()

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # Header
        header = ctk.CTkLabel(
            self,
            text="Dojo Nerd Stats",
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        header.grid(row=0, column=0, columnspan=2, padx=20, pady=(16, 4), sticky="w")

        subtitle = ctk.CTkLabel(
            self,
            text="Comparing all-time training history with the active session metrics.",
            font=ctk.CTkFont(size=11),
            text_color="#888888",
        )
        subtitle.grid(row=1, column=0, columnspan=2, padx=20, pady=(0, 16), sticky="w")

        # All-Time History Panel (Left Column)
        self.all_time_panel = ctk.CTkFrame(self, corner_radius=12)
        self.all_time_panel.grid(row=2, column=0, padx=(20, 10), pady=(0, 20), sticky="nsew")
        self.all_time_panel.grid_columnconfigure(0, weight=1)
        self.all_time_panel.grid_rowconfigure(2, weight=1)
        self.all_time_panel.grid_rowconfigure(4, weight=1)

        # All-Time Header
        all_time_title = ctk.CTkLabel(
            self.all_time_panel,
            text="All-Time History",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        all_time_title.grid(row=0, column=0, padx=15, pady=(12, 2), sticky="w")

        # All-Time Loss Graph
        all_time_loss_label = ctk.CTkLabel(
            self.all_time_panel, text="Loss", font=ctk.CTkFont(size=12, weight="bold")
        )
        all_time_loss_label.grid(row=1, column=0, padx=15, pady=(4, 2), sticky="sw")

        self.all_time_loss_graph = StatsMiniGraph(
            self.all_time_panel, title="", line_color="#ef4444"  # Red
        )
        self.all_time_loss_graph.grid(row=2, column=0, padx=15, pady=(0, 10), sticky="nsew")

        # All-Time Average Return Graph
        all_time_ret_label = ctk.CTkLabel(
            self.all_time_panel, text="Average Return", font=ctk.CTkFont(size=12, weight="bold")
        )
        all_time_ret_label.grid(row=3, column=0, padx=15, pady=(4, 2), sticky="sw")

        self.all_time_return_graph = StatsMiniGraph(
            self.all_time_panel, title="", line_color="#3b82f6"  # Blue
        )
        self.all_time_return_graph.grid(row=4, column=0, padx=15, pady=(0, 15), sticky="nsew")

        # Current Session Panel (Right Column)
        self.current_panel = ctk.CTkFrame(self, corner_radius=12)
        self.current_panel.grid(row=2, column=1, padx=(10, 20), pady=(0, 20), sticky="nsew")
        self.current_panel.grid_columnconfigure(0, weight=1)
        self.current_panel.grid_rowconfigure(2, weight=1)
        self.current_panel.grid_rowconfigure(4, weight=1)

        # Current Session Header
        current_title = ctk.CTkLabel(
            self.current_panel,
            text="Current/Last Session",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        current_title.grid(row=0, column=0, padx=15, pady=(12, 2), sticky="w")

        # Current Session Loss Graph
        current_loss_label = ctk.CTkLabel(
            self.current_panel, text="Loss", font=ctk.CTkFont(size=12, weight="bold")
        )
        current_loss_label.grid(row=1, column=0, padx=15, pady=(4, 2), sticky="sw")

        self.current_loss_graph = StatsMiniGraph(
            self.current_panel, title="", line_color="#ec4899", empty_text="No active session"  # Pink
        )
        self.current_loss_graph.grid(row=2, column=0, padx=15, pady=(0, 10), sticky="nsew")

        # Current Session Average Return Graph
        current_ret_label = ctk.CTkLabel(
            self.current_panel, text="Average Return", font=ctk.CTkFont(size=12, weight="bold")
        )
        current_ret_label.grid(row=3, column=0, padx=15, pady=(4, 2), sticky="sw")

        self.current_return_graph = StatsMiniGraph(
            self.current_panel, title="", line_color="#10b981", empty_text="No active session"  # Green
        )
        self.current_return_graph.grid(row=4, column=0, padx=15, pady=(0, 15), sticky="nsew")

        # Populate with any already-accumulated metrics from state
        self._refresh_from_state()

        # Register as a live listener for updates during training
        self._on_update = self._handle_metrics_update
        training_state_manager.register_nerd_stats_listener(self._on_update)

        # Unregister when the window closes
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _refresh_from_state(self):
        """Populates graphs with any metrics already accumulated in state."""
        self.all_time_loss_graph.set_data(list(training_state_manager.all_time_loss_history))
        self.all_time_return_graph.set_data(list(training_state_manager.all_time_return_history))
        self.current_loss_graph.set_data(list(training_state_manager.nerd_loss_history))
        self.current_return_graph.set_data(list(training_state_manager.nerd_return_history))

    def _handle_metrics_update(self, steps, losses, returns):
        """Called from the background thread — schedule UI update on the main thread."""
        self.after(0, self._apply_metrics_update)

    def _apply_metrics_update(self):
        """Applies the new data to the charts (always called on main thread)."""
        if not self.winfo_exists():
            return
        self._refresh_from_state()

    def _on_close(self):
        """Unregisters listener and destroys the window."""
        training_state_manager.unregister_nerd_stats_listener(self._on_update)
        self.destroy()

