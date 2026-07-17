import customtkinter as ctk

class TrajectoryMinimap(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="#2b2b2b", corner_radius=8, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.trajectory = None
        self.grid_size = None
        self.tile_size = None
        self.walls = []
        self.start_pos = None
        self.goal_pos = None

        self.minimap_title = ctk.CTkLabel(
            self, text="Path Visualizer", font=ctk.CTkFont(size=14, weight="bold")
        )
        self.minimap_title.grid(row=0, column=0, padx=12, pady=(12, 4), sticky="w")

        # Canvas for drawing the level map & path
        self.canvas = ctk.CTkCanvas(self, bg="#2b2b2b", highlightthickness=0)
        self.canvas.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="nsew")
        self.canvas.bind("<Configure>", lambda e: self.draw_minimap())

    def update_minimap(
        self, trajectory, grid_size, tile_size, walls, start_pos, goal_pos
    ):
        self.trajectory = trajectory
        self.grid_size = grid_size
        self.tile_size = tile_size
        self.walls = walls
        self.start_pos = start_pos
        self.goal_pos = goal_pos
        self.draw_minimap()

    def reset_to_default(self):
        self.trajectory = None
        self.grid_size = None
        self.tile_size = None
        self.walls = []
        self.start_pos = None
        self.goal_pos = None
        self.canvas.delete("all")

    def draw_minimap(self):
        """Draws the scaled level grid, walls, goal, and the continuous delver path."""
        self.canvas.delete("all")
        if not self.trajectory:
            return

        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()

        if canvas_w <= 1 or canvas_h <= 1:
            return

        grid_w, grid_h = self.grid_size if self.grid_size else (27, 27)
        tile_w, tile_h = self.tile_size if self.tile_size else (16, 16)

        margin = 15
        available_w = canvas_w - 2 * margin
        available_h = canvas_h - 2 * margin

        scale_x = available_w / grid_w
        scale_y = available_h / grid_h
        scale = min(scale_x, scale_y)

        # Center horizontally, anchor to top vertically
        offset_x = margin + (available_w - grid_w * scale) / 2
        offset_y = margin

        # Draw grid cells (background)
        for x in range(grid_w):
            for y in range(grid_h):
                cx1 = offset_x + x * scale
                cy1 = offset_y + y * scale
                cx2 = cx1 + scale
                cy2 = cy1 + scale
                self.canvas.create_rectangle(
                    cx1, cy1, cx2, cy2, outline="#2a2a2a", fill="#171717", width=1
                )

        # Draw walls (platforms)
        for wx, wy in self.walls:
            cx1 = offset_x + wx * scale
            cy1 = offset_y + wy * scale
            cx2 = cx1 + scale
            cy2 = cy1 + scale
            self.canvas.create_rectangle(
                cx1, cy1, cx2, cy2, outline="#3e3e3e", fill="#4f4f4f", width=1
            )

        # Draw Goal position (Amber circle with G)
        if self.goal_pos:
            gx, gy = self.goal_pos
            cx = offset_x + (gx + 0.5) * scale
            cy = offset_y + (gy + 0.5) * scale
            r = max(4.0, scale * 0.4)
            self.canvas.create_oval(
                cx - r,
                cy - r,
                cx + r,
                cy + r,
                fill="#f59e0b",
                outline="#d97706",
                width=2,
            )
            self.canvas.create_text(
                cx,
                cy,
                text="G",
                fill="#ffffff",
                font=("Arial", int(max(6, scale * 0.5)), "bold"),
            )

        # Parse continuous physical positions of the delver
        path_points = []
        for snapshot in self.trajectory.frame_snapshots:
            for entity in snapshot.entities:
                if entity.entity_id.lower().startswith("delver"):
                    path_points.append(entity.position)
                    break

        # Map physical points to tile space coordinates and scale them to the canvas
        canvas_points = []
        for px, py in path_points:
            gx = (px - tile_w / 2) / tile_w
            gy = (grid_h * tile_h - (py - tile_h / 2)) / tile_h

            cx = offset_x + gx * scale
            cy = offset_y + gy * scale
            canvas_points.append((cx, cy))

        # Draw continuous trajectory line (blue)
        if len(canvas_points) > 1:
            for i in range(len(canvas_points) - 1):
                p1 = canvas_points[i]
                p2 = canvas_points[i+1]
                self.canvas.create_line(
                    p1[0], p1[1], p2[0], p2[1],
                    fill="#3b82f6", width=3
                )

        # Draw Start position (Green circle with S)
        if self.start_pos:
            sx, sy = self.start_pos
            cx = offset_x + (sx + 0.5) * scale
            cy = offset_y + (sy + 0.5) * scale
            r = max(4.0, scale * 0.4)
            self.canvas.create_oval(
                cx - r, cy - r, cx + r, cy + r,
                fill="#10b981", outline="#059669", width=2
            )
            self.canvas.create_text(
                cx, cy, text="S", fill="#ffffff",
                font=("Arial", int(max(6, scale * 0.5)), "bold")
            )

        # Draw End position (colored dot with trophy or skull)
        if canvas_points:
            ex, ey = canvas_points[-1]
            r = max(5.0, scale * 0.4)
            end_color = "#10b981" if self.trajectory.victorious else "#ef4444"
            self.canvas.create_oval(
                ex - r, ey - r, ex + r, ey + r,
                fill=end_color, outline="#ffffff", width=2
            )
            marker_text = "🏆" if self.trajectory.victorious else "💀"
            self.canvas.create_text(
                ex, ey, text=marker_text, font=("Arial", int(max(7, scale * 0.5)))
            )
