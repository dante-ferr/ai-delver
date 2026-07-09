import customtkinter as ctk

class TrajectorySummaryPanel(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="#2b2b2b", corner_radius=8, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # Title
        self.summary_title = ctk.CTkLabel(
            self,
            text="Episode Summary",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.summary_title.pack(anchor="w", padx=12, pady=(12, 4))

        # Stats Container
        self.stats_container = ctk.CTkFrame(self, fg_color="transparent")
        self.stats_container.pack(fill="x", padx=12, pady=4)

        self.status_label = ctk.CTkLabel(
            self.stats_container,
            text="Select an episode to view stats.",
            font=ctk.CTkFont(size=13),
            justify="left"
        )
        self.status_label.pack(anchor="w", pady=4)

        # Timeline Title
        self.timeline_title = ctk.CTkLabel(
            self,
            text="Action Timeline",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.timeline_title.pack(anchor="w", padx=12, pady=(8, 4))

        # Scrollable Textbox for timeline events
        self.timeline_display = ctk.CTkTextbox(self, wrap="none")
        self.timeline_display.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    def update_summary(self, trajectory):
        """Updates the text statistics and action timeline from the trajectory."""
        outcome_str = "🏆 VICTORIOUS" if trajectory.victorious else "💀 DEFEATED"
        outcome_color = "#10b981" if trajectory.victorious else "#ef4444"
        
        # Calculate duration based on frame count and actions per second
        total_frames = len(trajectory.frame_snapshots)
        dur_secs = total_frames / trajectory.actions_per_second if trajectory.actions_per_second > 0 else 0.0

        summary_text = (
            f"Outcome:  {outcome_str}\n"
            f"Duration: {dur_secs:.2f}s ({total_frames} frames)"
        )
        self.status_label.configure(text=summary_text, text_color=outcome_color)

        # Update timeline display
        self.timeline_display.configure(state="normal")
        self.timeline_display.delete("1.0", "end")

        timeline = []
        prev_action = None
        for i, action in enumerate(trajectory.delver_actions):
            t = i / trajectory.actions_per_second if trajectory.actions_per_second > 0 else 0.0
            
            run_val = action.get("run", 0)
            jump_val = action.get("jump", False)
            
            # Log changes in action intent
            is_different = (
                prev_action is None or
                prev_action.get("run", 0) != run_val or
                prev_action.get("jump", False) != jump_val
            )
            
            if is_different:
                action_desc = []
                if run_val == 1:
                    action_desc.append("Run Right 👉")
                elif run_val == -1:
                    action_desc.append("Run Left 👈")
                
                if jump_val:
                    action_desc.append("Jump 🦘")
                
                if not action_desc:
                    action_desc.append("Idle 🧘")
                
                timeline.append(f"{t:.1f}s: " + " + ".join(action_desc))
                prev_action = action

        self.timeline_display.insert("1.0", "\n".join(timeline))
        self.timeline_display.configure(state="disabled")

    def reset_to_default(self):
        self.status_label.configure(text="Select an episode to view stats.", text_color="#ffffff")
        self.timeline_display.configure(state="normal")
        self.timeline_display.delete("1.0", "end")
        self.timeline_display.insert(
            "1.0",
            "Trajectory actions will be listed here chronologically once loaded."
        )
        self.timeline_display.configure(state="disabled")
