import customtkinter as ctk
from state_managers import trajectory_stats_state_manager, training_state_manager
from src.app.components import MouseWheelScrollableFrame
from app.fonts import app_font
from ._stats_mini_graph import StatsMiniGraph


class AllStatsWindow(ctk.CTkToplevel):
    """
    A Toplevel window that displays trajectory and deep learning training metrics
    as mini line charts, with paginated All-Time and Current / Latest Session views.
    """

    ALL_TIME = "All-Time"
    CURRENT_SESSION = "Current / Latest Session"
    GRAPH_HEIGHT = 180

    def __init__(self, master):
        super().__init__(master)
        self.title("Dojo All Stats")
        self.geometry("700x600")
        self.resizable(True, True)
        self.lift()
        self.focus_set()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        header = ctk.CTkLabel(
            self,
            text="Dojo All Stats",
            font=app_font(size=20, weight="bold"),
        )
        header.grid(row=0, column=0, padx=20, pady=(16, 4), sticky="w")

        subtitle = ctk.CTkLabel(
            self,
            text="Trajectory and training metrics across all-time history and the current or latest session.",
            font=app_font(size=11),
            text_color="#888888",
        )
        subtitle.grid(row=1, column=0, padx=20, pady=(0, 12), sticky="w")

        self.page_selector = ctk.CTkSegmentedButton(
            self,
            values=[self.ALL_TIME, self.CURRENT_SESSION],
            command=self._on_page_selected,
            font=app_font(size=13),
        )
        self.page_selector.set(self.ALL_TIME)
        self.page_selector.grid(row=2, column=0, padx=20, pady=(0, 12), sticky="ew")

        self.graphs_container = MouseWheelScrollableFrame(self, corner_radius=12)
        self.graphs_container.grid(row=3, column=0, padx=20, pady=(0, 20), sticky="nsew")
        self.graphs_container.grid_columnconfigure(0, weight=1)

        # All-Time graphs
        self.victories_graph = StatsMiniGraph(
            self.graphs_container,
            title="Accumulated Victories",
            line_color="#10b981",
            height=self.GRAPH_HEIGHT,
        )
        self.steps_graph = StatsMiniGraph(
            self.graphs_container,
            title="Trajectory Steps",
            line_color="#00ffff",
            height=self.GRAPH_HEIGHT,
        )
        self.all_time_loss_label = ctk.CTkLabel(
            self.graphs_container, text="Loss", font=app_font(size=12, weight="bold")
        )
        self.all_time_loss_graph = StatsMiniGraph(
            self.graphs_container, title="", line_color="#a8261b", height=self.GRAPH_HEIGHT
        )
        self.all_time_return_label = ctk.CTkLabel(
            self.graphs_container,
            text="Average Return",
            font=app_font(size=12, weight="bold"),
        )
        self.all_time_return_graph = StatsMiniGraph(
            self.graphs_container, title="", line_color="#3b82f6", height=self.GRAPH_HEIGHT
        )

        # Current Session graphs
        self.current_loss_label = ctk.CTkLabel(
            self.graphs_container, text="Loss", font=app_font(size=12, weight="bold")
        )
        self.current_loss_graph = StatsMiniGraph(
            self.graphs_container,
            title="",
            line_color="#ec4899",
            empty_text="No session data",
            height=self.GRAPH_HEIGHT,
        )
        self.current_return_label = ctk.CTkLabel(
            self.graphs_container,
            text="Average Return",
            font=app_font(size=12, weight="bold"),
        )
        self.current_return_graph = StatsMiniGraph(
            self.graphs_container,
            title="",
            line_color="#10b981",
            empty_text="No session data",
            height=self.GRAPH_HEIGHT,
        )

        self._show_all_time_page()
        self._refresh_from_state()

        self._on_metrics_update = self._handle_metrics_update
        self._on_stats_updated = self._handle_stats_updated
        training_state_manager.register_nerd_stats_listener(self._on_metrics_update)
        trajectory_stats_state_manager.add_on_stats_updated_callback(self._on_stats_updated)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_page_selected(self, value: str):
        if value == self.CURRENT_SESSION:
            self._show_current_session_page()
        else:
            self._show_all_time_page()

    def _clear_graphs_container(self):
        for widget in self.graphs_container.winfo_children():
            widget.pack_forget()

    def _show_all_time_page(self):
        self._clear_graphs_container()
        self.victories_graph.pack(fill="x", padx=10, pady=(10, 8))
        self.steps_graph.pack(fill="x", padx=10, pady=(0, 8))
        self.all_time_loss_label.pack(anchor="w", padx=15, pady=(4, 2))
        self.all_time_loss_graph.pack(fill="x", padx=10, pady=(0, 8))
        self.all_time_return_label.pack(anchor="w", padx=15, pady=(4, 2))
        self.all_time_return_graph.pack(fill="x", padx=10, pady=(0, 15))
        self.graphs_container.bind_scroll_events_recursively(self.graphs_container)

    def _show_current_session_page(self):
        self._clear_graphs_container()
        self.current_loss_label.pack(anchor="w", padx=15, pady=(10, 2))
        self.current_loss_graph.pack(fill="x", padx=10, pady=(0, 8))
        self.current_return_label.pack(anchor="w", padx=15, pady=(4, 2))
        self.current_return_graph.pack(fill="x", padx=10, pady=(0, 15))
        self.graphs_container.bind_scroll_events_recursively(self.graphs_container)

    def _refresh_from_state(self):
        """Populates graphs with any metrics already accumulated in state."""
        self.victories_graph.set_data(list(trajectory_stats_state_manager.victories_history))
        self.steps_graph.set_data(list(trajectory_stats_state_manager.steps_history))
        self.all_time_loss_graph.set_data(list(training_state_manager.all_time_loss_history))
        self.all_time_return_graph.set_data(list(training_state_manager.all_time_return_history))
        self.current_loss_graph.set_data(list(training_state_manager.nerd_loss_history))
        self.current_return_graph.set_data(list(training_state_manager.nerd_return_history))

    def _handle_metrics_update(self, steps, losses, returns):
        """Called from the background thread — schedule UI update on the main thread."""
        self.after(0, self._apply_metrics_update)

    def _handle_stats_updated(self):
        """Called when trajectory stats refresh completes."""
        self.after(0, self._apply_metrics_update)

    def _apply_metrics_update(self):
        """Applies the new data to the charts (always called on main thread)."""
        if not self.winfo_exists():
            return
        self._refresh_from_state()

    def _on_close(self):
        """Unregisters listeners and destroys the window."""
        training_state_manager.unregister_nerd_stats_listener(self._on_metrics_update)
        trajectory_stats_state_manager.remove_on_stats_updated_callback(self._on_stats_updated)
        self.destroy()
