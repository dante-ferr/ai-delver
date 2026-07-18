from .. import Page
from .trajectory_viewer import TrajectoryViewer
from .agent_panel import AgentPanel
from .train_panel import TrainPanel
from ._server_connection_panel import ServerConnectionPanel
from state_managers import training_state_manager
from app.components import LoadingLogsPanel
import customtkinter as ctk


class AgentPage(Page):
    """
    Responsive Agent page with three layout modes:
      - wide: Agent | Train | Trajectory
      - compact: (Agent/Train selector) | Trajectory
      - portrait: one full-width section via Agent / Train / Trajectory selector
    """

    MODE_WIDE = "wide"
    MODE_COMPACT = "compact"
    MODE_PORTRAIT = "portrait"

    WIDE_MIN_WIDTH = 1100
    COMPACT_MIN_WIDTH = 700
    PORTRAIT_ASPECT_RATIO = 0.85  # width/height below this => portrait

    PADDING_BY_MODE = {
        MODE_WIDE: 32,
        MODE_COMPACT: 20,
        MODE_PORTRAIT: 12,
    }

    SECTION_AGENT = "Agent"
    SECTION_TRAIN = "Train"
    SECTION_TRAJECTORY = "Trajectory"
    SIDE_SECTIONS = (SECTION_AGENT, SECTION_TRAIN)
    ALL_SECTIONS = (SECTION_AGENT, SECTION_TRAIN, SECTION_TRAJECTORY)

    DEBOUNCE_MS = 80

    def __init__(self, master):
        super().__init__(master, "Agent")

        self._layout_mode: str | None = None
        self._layout_key: tuple | None = None
        self._active_section = self.SECTION_TRAJECTORY
        self._configure_after_id: str | None = None
        self._column_padding = self.PADDING_BY_MODE[self.MODE_WIDE]

        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.section_selector = ctk.CTkSegmentedButton(
            self,
            values=list(self.ALL_SECTIONS),
            command=self._on_section_selected,
            font=ctk.CTkFont(size=13),
        )
        self.section_selector.set(self._active_section)

        # Column frames are parented directly to the page so CTk nested-frame
        # coloring (top_fg_color) matches the original Train column look.
        self.agent_col = ctk.CTkFrame(self, fg_color="transparent")
        self.train_col = ctk.CTkFrame(self)
        self.trajectory_col = ctk.CTkFrame(self, fg_color="transparent")

        self._agent_panel = AgentPanel(self.agent_col)
        self._agent_panel.pack(padx=0, pady=0, fill="both", expand=True)

        self.train_panel_frame = ctk.CTkFrame(self.train_col, fg_color="transparent")
        self.train_panel_frame.pack(padx=0, pady=0, fill="both", expand=True)

        self.train_panel = TrainPanel(self.train_panel_frame)
        self.server_connection_panel = ServerConnectionPanel(self.train_panel_frame)
        self.server_loading_logs_panel = LoadingLogsPanel(self.train_panel_frame)
        self.server_loading_logs_panel.pack(padx=0, pady=0, fill="x")

        self.trajectory_viewer = TrajectoryViewer(self.trajectory_col)
        self.trajectory_viewer.pack(padx=0, pady=0, fill="both", expand=True)

        training_state_manager.add_callback(
            "connected_to_server", self._on_connected_to_server_status_change
        )
        self._on_connected_to_server_status_change(
            training_state_manager.get_value("connected_to_server")
        )

        # CTk fires Configure on an internal widget, so do not filter by event.widget.
        self.bind("<Configure>", self._on_configure, add="+")
        self.after(0, self._apply_layout)

    # ------------------------------------------------------------------ layout

    def _on_configure(self, _event=None):
        if self._configure_after_id is not None:
            try:
                self.after_cancel(self._configure_after_id)
            except Exception:
                pass
        self._configure_after_id = self.after(self.DEBOUNCE_MS, self._apply_layout)

    def _resolve_mode(self, width: int, height: int) -> str:
        if width <= 1 or height <= 1:
            return self._layout_mode or self.MODE_WIDE

        aspect = width / max(height, 1)
        if width < self.COMPACT_MIN_WIDTH or aspect < self.PORTRAIT_ASPECT_RATIO:
            return self.MODE_PORTRAIT
        if width < self.WIDE_MIN_WIDTH:
            return self.MODE_COMPACT
        return self.MODE_WIDE

    def _apply_layout(self):
        self._configure_after_id = None

        width = self.winfo_width()
        height = self.winfo_height()
        mode = self._resolve_mode(width, height)
        padding = self.PADDING_BY_MODE[mode]

        if mode == self.MODE_COMPACT:
            if self._active_section not in self.SIDE_SECTIONS:
                self._active_section = self.SECTION_TRAIN
            section = self._active_section
        elif mode == self.MODE_PORTRAIT:
            if self._active_section not in self.ALL_SECTIONS:
                self._active_section = self.SECTION_TRAJECTORY
            section = self._active_section
        else:
            section = None

        layout_key = (mode, padding, section)
        if layout_key == self._layout_key:
            return

        self._layout_mode = mode
        self._layout_key = layout_key
        self._column_padding = padding
        self._clear_layout_grid()

        if mode == self.MODE_WIDE:
            self._layout_wide()
        elif mode == self.MODE_COMPACT:
            self._layout_compact()
        else:
            self._layout_portrait()

        self._apply_panel_padding()

    def _clear_layout_grid(self):
        for child in (self.agent_col, self.train_col, self.trajectory_col):
            child.grid_forget()

        # Reset column/row config and clear any leftover uniform groups.
        for col in range(3):
            self.grid_columnconfigure(col, weight=0, minsize=0, uniform="")
        for row in (0, 1):
            self.grid_rowconfigure(row, weight=0 if row == 0 else 1, minsize=0)

        self.section_selector.grid_forget()

    def _layout_wide(self):
        self.grid_rowconfigure(1, weight=1)
        for col, weight in enumerate((1, 2, 3)):
            self.grid_columnconfigure(
                col, weight=weight, uniform="agent_page_columns"
            )

        self.agent_col.grid(row=1, column=0, sticky="nsew")
        self.train_col.grid(row=1, column=1, sticky="nsew")
        self.trajectory_col.grid(row=1, column=2, sticky="nsew")

    def _layout_compact(self):
        self.section_selector.configure(values=list(self.SIDE_SECTIONS))
        self.section_selector.set(self._active_section)
        self.section_selector.grid(
            row=0, column=0, columnspan=2, sticky="ew",
            padx=self._column_padding, pady=(8, 0),
        )

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=2, uniform="agent_compact")
        self.grid_columnconfigure(1, weight=3, uniform="agent_compact")

        side_col = (
            self.agent_col
            if self._active_section == self.SECTION_AGENT
            else self.train_col
        )
        side_col.grid(row=1, column=0, sticky="nsew")
        self.trajectory_col.grid(row=1, column=1, sticky="nsew")

    def _layout_portrait(self):
        self.section_selector.configure(values=list(self.ALL_SECTIONS))
        self.section_selector.set(self._active_section)
        self.section_selector.grid(
            row=0, column=0, sticky="ew",
            padx=self._column_padding, pady=(8, 0),
        )

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        active_col = {
            self.SECTION_AGENT: self.agent_col,
            self.SECTION_TRAIN: self.train_col,
            self.SECTION_TRAJECTORY: self.trajectory_col,
        }[self._active_section]
        active_col.grid(row=1, column=0, sticky="nsew")

    def _apply_panel_padding(self):
        pad = self._column_padding
        for panel in (
            self._agent_panel,
            self.train_panel_frame,
            self.trajectory_viewer,
        ):
            panel.pack_configure(padx=pad, pady=pad)

    def _on_section_selected(self, value: str):
        if value == self._active_section:
            return
        self._active_section = value
        self._apply_layout()

    # ---------------------------------------------------------- server status

    def _on_connected_to_server_status_change(self, connected_to_server: str):
        if connected_to_server == "yes":
            self.server_connection_panel.pack_forget()
            self.train_panel.pack(padx=0, pady=0, fill="both", expand=True)
            self.server_loading_logs_panel.remove_log("loading_server")

        elif connected_to_server == "no":
            self.train_panel.pack_forget()
            self.server_connection_panel.pack(padx=0, pady=0, fill="both", expand=True)
            self.server_loading_logs_panel.remove_log("loading_server")

        elif connected_to_server == "loading":
            self.train_panel.pack_forget()
            self.server_connection_panel.pack_forget()
            self.server_loading_logs_panel.show_log(
                "loading_server", "Loading server..."
            )
