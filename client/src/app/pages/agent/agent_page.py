from .. import Page
from .trajectory_viewer import TrajectoryViewer
from .agent_panel import AgentPanel
from .train_panel import TrainPanel
from ._server_connection_panel import ServerConnectionPanel
from state_managers import training_state_manager
from app.components import LoadingLogsPanel
import customtkinter as ctk

class AgentPage(Page):
    COLUMN_PADDING = 32
    COLUMN_KWARGS = {
        "row": 0,
        "padx": 0,
        "pady": 0,
        "sticky": "nsew",
    }

    def __init__(self, master):
        super().__init__(master, "Agent")

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=0, minsize=128)
        self.grid_columnconfigure(1, weight=0, minsize=500)
        self.grid_columnconfigure(2, weight=1, minsize=128)

        col_frame_1 = ctk.CTkFrame(self, width=128, fg_color="transparent")
        col_frame_1.grid(column=0, **self.COLUMN_KWARGS)
        agent_panel = AgentPanel(col_frame_1)
        agent_panel.pack(
            padx=self.COLUMN_PADDING, pady=self.COLUMN_PADDING, fill="both", expand=True
        )

        col_frame_2 = ctk.CTkFrame(self, width=500)
        col_frame_2.grid(column=1, **self.COLUMN_KWARGS)
        self.train_panel_frame = ctk.CTkFrame(col_frame_2, fg_color="transparent")
        self.train_panel_frame.pack(
            padx=self.COLUMN_PADDING, pady=self.COLUMN_PADDING, fill="both", expand=True
        )

        self.train_panel = TrainPanel(self.train_panel_frame)
        self.server_connection_panel = ServerConnectionPanel(self.train_panel_frame)

        self.server_loading_logs_panel = LoadingLogsPanel(self.train_panel_frame)
        self.server_loading_logs_panel.pack(padx=0, pady=0, fill="x")

        col_frame_3 = ctk.CTkFrame(self, fg_color="transparent")
        col_frame_3.grid(column=2, **self.COLUMN_KWARGS)
        trajectory_viewer = TrajectoryViewer(col_frame_3)
        trajectory_viewer.pack(
            padx=self.COLUMN_PADDING, pady=self.COLUMN_PADDING, fill="both", expand=True
        )

        training_state_manager.add_callback(
            "connected_to_server", self._on_connected_to_server_status_change
        )
        self._on_connected_to_server_status_change(
            training_state_manager.get_value("connected_to_server")
        )

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
