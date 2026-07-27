import customtkinter as ctk
from ._agent_save_button import AgentSaveButton
from ._agent_load_button import AgentLoadButton, AgentAutosaveCheckbox
from ._agent_delete_button import AgentDeleteButton
from ._agent_restore_checkpoint_button import AgentRestoreCheckpointButton
from ._agent_new_session_button import AgentNewSessionButton


class AgentFileContainer(ctk.CTkFrame):

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")

        autosave = AgentAutosaveCheckbox(self)
        autosave.pack(side="top", anchor="w", padx=0, pady=(0, 6))

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(side="top", fill="x", padx=0, pady=0)

        restore_button = AgentRestoreCheckpointButton(actions)
        restore_button.pack(side="left", padx=0, pady=0)

        new_button = AgentNewSessionButton(actions)
        new_button.pack(side="left", padx=(8, 0), pady=0)

        icons = ctk.CTkFrame(self, fg_color="transparent")
        icons.pack(side="top", fill="x", padx=0, pady=(6, 0))

        save_button = AgentSaveButton(icons)
        save_button.pack(side="left", padx=0, pady=0)

        load_button = AgentLoadButton(icons)
        load_button.pack(side="left", padx=0, pady=0)

        delete_button = AgentDeleteButton(icons)
        delete_button.pack(side="left", padx=0, pady=0)
