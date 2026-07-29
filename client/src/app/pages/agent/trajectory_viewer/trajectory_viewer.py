import customtkinter as ctk
import json
from typing import TYPE_CHECKING
from .header import TrajectoryHeader
from .summary_panel import TrajectorySummaryPanel
from .path_visualizer import TrajectoryMinimap, PathVisualizerPopup
from app.components import StandardButton, MouseWheelScrollableFrame

if TYPE_CHECKING:
    from runtime.episode_trajectory import EpisodeTrajectory


class TrajectoryViewer(ctk.CTkFrame):
    STACK_BELOW_WIDTH = 520
    DEBOUNCE_MS = 80

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.trajectory: "EpisodeTrajectory | None" = None
        self._stacked: bool | None = None
        self._configure_after_id: str | None = None
        self._header_width_after_id: str | None = None
        self._last_header_width: int | None = None

        self._path_popup: PathVisualizerPopup | None = None
        self._last_minimap_args = None

        # Main content area on Row 1 (Unified Scrollable Container)
        self.content_frame = MouseWheelScrollableFrame(self, fg_color="transparent")
        self.content_frame.configure(border_width=0)
        self.content_frame.grid(row=1, column=0, padx=8, pady=(4, 8), sticky="nsew")

        # Left panel: Summary & timeline
        self.summary_panel = TrajectorySummaryPanel(self.content_frame)

        # Right panel: 2D Minimap Visualizer + expand control
        self.minimap_column = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.minimap_column.grid_columnconfigure(0, weight=1)
        self.minimap_column.grid_rowconfigure(1, weight=1)

        self.minimap_toolbar = ctk.CTkFrame(self.minimap_column, fg_color="transparent")
        self.minimap_toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 2))
        self.minimap_toolbar.grid_columnconfigure(0, weight=1)

        self.expand_path_btn = StandardButton(
            self.minimap_toolbar,
            text="Expand",
            width=80,
            height=26,
            command=self._open_path_popup,
        )
        self.expand_path_btn.grid(row=0, column=1, sticky="e")

        self.minimap_panel = TrajectoryMinimap(self.minimap_column)
        self.minimap_panel.grid(row=1, column=0, sticky="nsew")

        self._apply_content_layout(stacked=False)

        # Set default text before instantiating the header, so it gets overridden by the auto-load
        self._set_data_display_to_default()

        # Header on Row 0 - Configured last because it auto-triggers display_trajectory
        header = TrajectoryHeader(self)
        header.grid(row=0, column=0, padx=8, pady=(0, 4), sticky="ew")
        self.header = header

        self.content_frame.bind("<Configure>", self._on_content_configure, add="+")
        self.bind("<Configure>", self._on_viewer_configure, add="+")
        self.after(0, self._sync_header_width)

    def _on_content_configure(self, _event=None):
        if self._configure_after_id is not None:
            try:
                self.after_cancel(self._configure_after_id)
            except Exception:
                pass
        self._configure_after_id = self.after(
            self.DEBOUNCE_MS, self._update_content_layout
        )

    def _on_viewer_configure(self, _event=None):
        # Debounce: continuous Configure ↔ width sync was shaking the panels.
        if self._header_width_after_id is not None:
            try:
                self.after_cancel(self._header_width_after_id)
            except Exception:
                pass
        self._header_width_after_id = self.after(
            self.DEBOUNCE_MS, self._sync_header_width
        )

    def _sync_header_width(self):
        self._header_width_after_id = None
        width = self.winfo_width()
        if width <= 1:
            width = self.content_frame.winfo_width()
        if width <= 1 or not hasattr(self, "header"):
            return
        width = max(160, width - 16)
        if self._last_header_width is not None and abs(width - self._last_header_width) < 4:
            return
        self._last_header_width = width
        self.header.set_header_width(width)

    def _update_content_layout(self):
        self._configure_after_id = None
        width = self.content_frame.winfo_width()
        if width <= 1:
            return
        self._apply_content_layout(stacked=width < self.STACK_BELOW_WIDTH)
        self._sync_header_width()
        self.content_frame.bind_scroll_events_recursively(self.content_frame)
        self.content_frame.after(50, self.content_frame._check_scroll_visibility)

    def _apply_content_layout(self, stacked: bool):
        if stacked == self._stacked:
            return
        self._stacked = stacked

        for col in range(2):
            self.content_frame.grid_columnconfigure(col, weight=0, minsize=0)
        for row in range(2):
            self.content_frame.grid_rowconfigure(row, weight=0, minsize=0)

        if stacked:
            # Minimap on top (visual-first), summary below.
            self.content_frame.grid_columnconfigure(0, weight=1)
            self.content_frame.grid_rowconfigure(0, weight=2, minsize=180)
            self.content_frame.grid_rowconfigure(1, weight=3, minsize=140)
            self.minimap_column.grid(
                row=0, column=0, padx=0, pady=(0, 4), sticky="nsew"
            )
            self.summary_panel.grid(
                row=1, column=0, padx=0, pady=(4, 0), sticky="nsew"
            )
        else:
            self.content_frame.grid_columnconfigure(0, weight=2)
            self.content_frame.grid_columnconfigure(1, weight=3)
            self.content_frame.grid_rowconfigure(0, weight=1)
            self.summary_panel.grid(
                row=0, column=0, padx=(0, 4), pady=0, sticky="nsew"
            )
            self.minimap_column.grid(
                row=0, column=1, padx=(4, 0), pady=0, sticky="nsew"
            )

    def display_trajectory(self):
        """Processes the trajectory and updates the summary, timeline, and 2D map."""
        if self.trajectory is None:
            raise ValueError("Trajectory is not loaded.")

        # Reset level metadata variables
        grid_size = None
        tile_size = None
        walls = []
        start_pos = None
        goal_pos = None

        # Try to load level save for this trajectory
        try:
            level_hash = self.trajectory.level_hash
            from loaders import agent_loader
            from src.app.utils.level_minimap_geometry import parse_level_minimap_geometry

            trajectory_loader = agent_loader.agent.trajectory_loader
            level_path = (
                trajectory_loader.trajectory_dir.parent
                / "level_saves"
                / f"{level_hash}.json"
            )

            if level_path.is_file():
                with open(level_path, "r") as f:
                    level_data = json.load(f)
                geom = parse_level_minimap_geometry(level_data)
                grid_size = geom.grid_size
                tile_size = geom.tile_size
                walls = geom.walls
                start_pos = geom.start_pos
                goal_pos = geom.goal_pos
        except Exception as e:
            print(f"[Visualizer Error] Failed to parse level file: {e}")

        # Update canvas height dynamically for vertical levels (grid_h > grid_w)
        if grid_size and grid_size[1] > grid_size[0]:
            aspect = grid_size[1] / max(1, grid_size[0])
            target_h = max(280, min(650, int(300 * aspect)))
            self.minimap_panel.canvas.configure(height=target_h)
        else:
            self.minimap_panel.canvas.configure(height=280)

        # Update left summary/timeline panel
        self.summary_panel.update_summary(self.trajectory)

        # Update right minimap panel (+ expanded popup if open)
        self._last_minimap_args = (
            self.trajectory,
            grid_size,
            tile_size,
            walls,
            start_pos,
            goal_pos,
        )
        self.minimap_panel.update_minimap(*self._last_minimap_args, animate=True)
        if self._path_popup is not None and self._path_popup.winfo_exists():
            self._path_popup.sync(*self._last_minimap_args, animate=True)

        self.content_frame.bind_scroll_events_recursively(self.content_frame)
        self.content_frame.after(50, self.content_frame._check_scroll_visibility)

    def _open_path_popup(self):
        if self._path_popup is not None and self._path_popup.winfo_exists():
            self._path_popup.lift()
            self._path_popup.focus_set()
            if self._last_minimap_args is not None:
                self._path_popup.sync(*self._last_minimap_args, animate=False)
            return
        self._path_popup = PathVisualizerPopup(self, self)
        if self._last_minimap_args is not None:
            self._path_popup.sync(*self._last_minimap_args, animate=True)
        elif self.trajectory is not None:
            self.display_trajectory()

    def _set_data_display_to_default(self):
        self.summary_panel.reset_to_default()
        self.minimap_panel.reset_to_default()
        self._last_minimap_args = None
        if self._path_popup is not None and self._path_popup.winfo_exists():
            self._path_popup.sync(None, None, None, [], None, None)
        self.content_frame.bind_scroll_events_recursively(self.content_frame)
        self.content_frame.after(50, self.content_frame._check_scroll_visibility)
