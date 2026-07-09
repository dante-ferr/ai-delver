import customtkinter as ctk
from tkinter import messagebox
from typing import TYPE_CHECKING, List
from app.components import Overlay, StandardButton
from src.config import config

if TYPE_CHECKING:
    from pytiling import Direction


class ResizeLevelDialog(Overlay):
    """
    A dialog window to get user input for level resizing.
    It prompts for a direction (top, bottom, left, right) and an amount.
    The user can select whether to expand or reduce the level.
    """

    def __init__(self, master):
        from state_managers.canvas_state_manager import canvas_state_manager

        super().__init__(master)

        self.title("Resize Grid")
        self.geometry("300x400")
        self.transient(master)  # Keep window on top of the master
        self.resizable(False, False)

        self._direction_top = ctk.BooleanVar(value=False)
        self._direction_bottom = ctk.BooleanVar(value=False)
        self._direction_left = ctk.BooleanVar(value=False)
        self._direction_right = ctk.BooleanVar(value=True)
        self._amount = ctk.StringVar(value="1")
        self._operation = ctk.StringVar(value="Expand")
        self._dynamic_resizing_var = canvas_state_manager.vars["dynamic_resizing"]

        self._create_widgets()

        # This is crucial to wait for the user to close the dialog
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self._post_init_config()
        self.wait_window(self)

    def _create_widgets(self):
        """Creates and places the widgets in the dialog."""
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(expand=True, fill="both", padx=15, pady=15)

        # --- Dynamic Resizing Toggle ---
        dynamic_resize_switch = ctk.CTkSwitch(
            main_frame,
            text="Dynamic resizing (it may be too slow)",
            variable=self._dynamic_resizing_var,
            command=self._toggle_manual_controls,
            font=ctk.CTkFont(size=config.STYLE.FONT.STANDARD_SIZE),
        )
        dynamic_resize_switch.pack(anchor="w", pady=(0, 15))

        # --- Manual Resizing Frame ---
        self._manual_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        self._manual_frame.pack(fill="both", expand=True)

        # --- Operation Selection ---
        operation_label = ctk.CTkLabel(
            self._manual_frame,
            text="Operation:",
            font=ctk.CTkFont(size=config.STYLE.FONT.STANDARD_SIZE),
        )
        operation_label.pack(pady=(0, 5), anchor="w")

        self._operation_selector = ctk.CTkSegmentedButton(
            self._manual_frame, values=["Expand", "Reduce"], variable=self._operation
        )
        self._operation_selector.pack(fill="x", pady=(0, 15))

        # --- Direction Selection ---
        direction_label = ctk.CTkLabel(
            self._manual_frame,
            text="Direction:",
            font=ctk.CTkFont(size=config.STYLE.FONT.STANDARD_SIZE),
        )
        direction_label.pack(pady=(0, 10), anchor="w")

        self._check_top = ctk.CTkCheckBox(
            self._manual_frame, text="Top", variable=self._direction_top
        )
        self._check_top.pack(anchor="w", padx=20)

        self._check_bottom = ctk.CTkCheckBox(
            self._manual_frame, text="Bottom", variable=self._direction_bottom
        )
        self._check_bottom.pack(anchor="w", padx=20)

        self._check_left = ctk.CTkCheckBox(
            self._manual_frame, text="Left", variable=self._direction_left
        )
        self._check_left.pack(anchor="w", padx=20)

        self._check_right = ctk.CTkCheckBox(
            self._manual_frame, text="Right", variable=self._direction_right
        )
        self._check_right.pack(anchor="w", padx=20)

        # --- Amount Input ---
        amount_label = ctk.CTkLabel(
            self._manual_frame,
            text="Amount (tiles):",
            font=ctk.CTkFont(size=config.STYLE.FONT.STANDARD_SIZE),
        )
        amount_label.pack(pady=(15, 5), anchor="w")

        self._amount_entry = ctk.CTkEntry(self._manual_frame, textvariable=self._amount)
        self._amount_entry.pack(fill="x")
        self._amount_entry.focus()  # Set focus to the entry box

        # --- Buttons ---
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.pack(fill="x", padx=15, pady=(0, 15))
        button_frame.grid_columnconfigure((0, 1), weight=1)

        self._confirm_button = StandardButton(
            button_frame, text="Confirm", command=self._on_confirm
        )
        self._confirm_button.grid(row=0, column=0, padx=(0, 5), sticky="ew")

        cancel_button = StandardButton(
            button_frame,
            text="Cancel",
            fg_color="#D33",
            hover_color="#C00",
            command=self._on_cancel,
        )
        cancel_button.grid(row=0, column=1, padx=(5, 0), sticky="ew")

        self._toggle_manual_controls()

    def _toggle_manual_controls(self):
        """Enables or disables manual resizing controls based on the switch state."""
        is_dynamic = self._dynamic_resizing_var.get()
        new_state = "disabled" if is_dynamic else "normal"

        self._operation_selector.configure(state=new_state)
        self._check_top.configure(state=new_state)
        self._check_bottom.configure(state=new_state)
        self._check_left.configure(state=new_state)
        self._check_right.configure(state=new_state)
        self._amount_entry.configure(state=new_state)
        self._confirm_button.configure(state=new_state)

    def _get_selected_directions(self) -> List["Direction"]:
        """Returns a list of selected direction strings."""
        directions: List["Direction"] = []
        if self._direction_top.get():
            directions.append("top")
        if self._direction_bottom.get():
            directions.append("bottom")
        if self._direction_left.get():
            directions.append("left")
        if self._direction_right.get():
            directions.append("right")
        return directions

    def _on_confirm(self):
        """Handle the confirm button click."""
        from loaders import level_loader

        try:
            # Validate that the amount is a positive integer
            amount = int(self._amount.get())
            if amount <= 0:
                raise ValueError("Amount must be positive.")
        except ValueError:
            messagebox.showerror(
                "Invalid Amount",
                "Please provide a positive integer value for the amount.",
                master=self,
            )
            self._amount.set("1")
            return

        directions = self._get_selected_directions()
        if not directions:
            messagebox.showwarning(
                "No Direction", "Please select at least one direction.", master=self
            )
            return

        operation = self._operation.get()
        if operation == "Expand":
            level_loader.level.map.multidirectional_expand_towards(directions, amount)
        elif operation == "Reduce":
            level_loader.level.map.multidirectional_reduce_towards(
                directions, abs(amount)
            )

        self.destroy()

    def _on_cancel(self):
        """Handle window close or cancel button click."""
        self.destroy()
