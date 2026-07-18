import customtkinter as ctk
import json
from typing import TYPE_CHECKING
from ._header import TrajectoryHeader
from ._summary_panel import TrajectorySummaryPanel
from ._minimap import TrajectoryMinimap

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

        # Main content area on Row 1 (Split layout) - Configured first to avoid init-order errors
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.grid(row=1, column=0, padx=8, pady=(4, 8), sticky="nsew")

        # Left panel: Summary & timeline
        self.summary_panel = TrajectorySummaryPanel(self.content_frame)

        # Right panel: 2D Minimap Visualizer
        self.minimap_panel = TrajectoryMinimap(self.content_frame)

        self._apply_content_layout(stacked=False)

        # Set default text before instantiating the header, so it gets overridden by the auto-load
        self._set_data_display_to_default()

        # Header on Row 0 - Configured last because it auto-triggers display_trajectory
        header = TrajectoryHeader(self)
        header.grid(row=0, column=0, padx=8, pady=(0, 4), sticky="w")
        self.header = header

        self.content_frame.bind("<Configure>", self._on_content_configure, add="+")
        self.summary_panel.bind("<Configure>", self._on_summary_configure, add="+")
        self.after(0, self._sync_slider_to_timeline)

    def _on_content_configure(self, _event=None):
        if self._configure_after_id is not None:
            try:
                self.after_cancel(self._configure_after_id)
            except Exception:
                pass
        self._configure_after_id = self.after(
            self.DEBOUNCE_MS, self._update_content_layout
        )

    def _on_summary_configure(self, _event=None):
        self._sync_slider_to_timeline()

    def _sync_slider_to_timeline(self):
        width = self.summary_panel.winfo_width()
        if width > 1 and hasattr(self, "header"):
            self.header.set_slider_width(width)

    def _update_content_layout(self):
        self._configure_after_id = None
        width = self.content_frame.winfo_width()
        if width <= 1:
            return
        self._apply_content_layout(stacked=width < self.STACK_BELOW_WIDTH)
        self._sync_slider_to_timeline()

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
            self.minimap_panel.grid(
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
            self.minimap_panel.grid(
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
            trajectory_loader = agent_loader.agent.trajectory_loader
            level_path = trajectory_loader.trajectory_dir.parent / "level_saves" / f"{level_hash}.json"
            
            if level_path.is_file():
                with open(level_path, "r") as f:
                    level_data = json.load(f)
                    map_data = level_data.get("map", {})
                    grid_size = map_data.get("grid_size", [27, 27])
                    tile_size = map_data.get("tile_size", [16, 16])
                    
                    # Load walls (platforms layer)
                    tilemap = map_data.get("tilemap", {})
                    for layer in tilemap.get("layers", []):
                        if layer.get("name") == "platforms":
                            for elem in layer.get("elements", []):
                                if elem.get("name") == "platform":
                                    pos = elem.get("position")
                                    if pos:
                                        walls.append((pos[0], pos[1]))
                    
                    # Load essentials (delver start, goal position)
                    world_objects_map = map_data.get("world_objects_map", {})
                    for layer in world_objects_map.get("layers", []):
                        if layer.get("name") == "essentials":
                            for elem in layer.get("elements", []):
                                name = elem.get("name")
                                pos = elem.get("position")
                                if pos:
                                    if name == "delver":
                                        start_pos = (pos[0], pos[1])
                                    elif name == "goal":
                                        goal_pos = (pos[0], pos[1])
        except Exception as e:
            print(f"[Visualizer Error] Failed to parse level file: {e}")

        # Update left summary/timeline panel
        self.summary_panel.update_summary(self.trajectory)

        # Update right minimap panel
        self.minimap_panel.update_minimap(self.trajectory, grid_size, tile_size, walls, start_pos, goal_pos)

    def _set_data_display_to_default(self):
        self.summary_panel.reset_to_default()
        self.minimap_panel.reset_to_default()
