import math
import customtkinter as ctk

from src.config import config


class TrajectoryMinimap(ctk.CTkFrame):
    """Path visualizer with size-independent diagonal reveal + staggered tile grow."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="#2b2b2b", corner_radius=8, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        pv = config.PATH_VISUALIZER
        self._tick_ms = int(pv.TICK_MS)
        self._tile_reveal_ms = int(pv.TILE_REVEAL_MS)
        self._tile_wipe_ms = int(pv.TILE_WIPE_MS)
        self._path_reveal_ms = int(pv.PATH_REVEAL_MS)
        self._grow_frames = int(pv.GROW_FRAMES)
        self._debounce_ms = int(pv.DEBOUNCE_MS)

        self.trajectory = None
        self.grid_size = None
        self.tile_size = None
        self.walls = []
        self.start_pos = None
        self.goal_pos = None

        self._anim_after_id = None
        self._configure_after_id = None
        self._layout = None
        self._has_drawn_content = False
        self._tiles_complete = False
        self._growing = []  # [{ids, cx, cy, half, age, is_wall}, ...]
        self._level_hash = None
        self._anim_gen = 0
        self._tiles_done = True
        self._path_done = True
        self._tile_next_d = 0
        self._diags_per_tick = 1
        self._path_idx = 0
        self._path_batch = 1

        self.minimap_title = ctk.CTkLabel(
            self, text="Path Visualizer", font=ctk.CTkFont(size=14, weight="bold")
        )
        self.minimap_title.grid(row=0, column=0, padx=12, pady=(12, 4), sticky="w")

        self.canvas = ctk.CTkCanvas(self, bg="#2b2b2b", highlightthickness=0)
        self.canvas.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="nsew")
        self.canvas.bind("<Configure>", self._on_configure)

    def update_minimap(
        self, trajectory, grid_size, tile_size, walls, start_pos, goal_pos
    ):
        self._cancel_animation()
        new_hash = getattr(trajectory, "level_hash", None) or ""
        # Only skip tile animation when the floor is fully drawn for this level.
        # Mid-reveal switches must restart tiles — _has_drawn_content alone is not enough.
        same_level = (
            bool(new_hash)
            and new_hash == self._level_hash
            and self._tiles_complete
        )

        self.trajectory = trajectory
        self.grid_size = grid_size
        self.tile_size = tile_size
        self.walls = walls
        self.start_pos = start_pos
        self.goal_pos = goal_pos
        self._level_hash = new_hash or None
        self._growing = []

        if same_level:
            # Keep floor/walls; only re-animate the trajectory path
            self.canvas.delete("path")
            self.canvas.delete("marker")
            self._start_path_only()
        else:
            self.canvas.delete("all")
            self._has_drawn_content = False
            self._tiles_complete = False
            self._start_reveal()

    def reset_to_default(self):
        self._cancel_animation()
        if self._has_drawn_content and self._layout is not None:
            self._start_wipe()
            return

        self._clear_state()
        self.canvas.delete("all")
        self._growing = []
        self._has_drawn_content = False
        self._tiles_complete = False

    def draw_minimap(self):
        """Synchronous full redraw (used after resize)."""
        self._cancel_animation()
        self.canvas.delete("all")
        self._growing = []
        self._has_drawn_content = False
        self._tiles_complete = False
        if not self.trajectory:
            self._layout = None
            return

        layout = self._compute_layout()
        if layout is None:
            self._layout = None
            return

        self._layout = layout
        self._draw_full(layout)
        self._has_drawn_content = True
        self._tiles_complete = True
        self._level_hash = getattr(self.trajectory, "level_hash", None) or self._level_hash

    # --- Configure debounce -------------------------------------------------

    def _on_configure(self, _event=None):
        if self._configure_after_id is not None:
            try:
                self.after_cancel(self._configure_after_id)
            except Exception:
                pass
        self._configure_after_id = self.after(
            self._debounce_ms, self._on_configure_debounced
        )

    def _on_configure_debounced(self):
        self._configure_after_id = None
        self.draw_minimap()

    def _cancel_configure(self):
        if self._configure_after_id is not None:
            try:
                self.after_cancel(self._configure_after_id)
            except Exception:
                pass
            self._configure_after_id = None

    # --- Animation helpers --------------------------------------------------

    def _cancel_animation(self):
        if self._anim_after_id is not None:
            try:
                self.after_cancel(self._anim_after_id)
            except Exception:
                pass
            self._anim_after_id = None
        # Invalidate any tick/wipe already mid-flight
        self._anim_gen += 1
        self._tiles_done = True
        self._path_done = True
        self._growing = []

    def _schedule_tick(self):
        gen = self._anim_gen
        self._anim_after_id = self.after(self._tick_ms, lambda: self._anim_tick(gen))

    def _clear_state(self):
        self.trajectory = None
        self.grid_size = None
        self.tile_size = None
        self.walls = []
        self.start_pos = None
        self.goal_pos = None
        self._layout = None
        self._growing = []
        self._level_hash = None
        self._tiles_complete = False
    @staticmethod
    def _items_per_tick(total_items, duration_ms, tick_ms):
        """How many items to process each tick so total_items finish in duration_ms."""
        num_ticks = max(1, duration_ms // tick_ms)
        return max(1, math.ceil(total_items / num_ticks))

    # --- Layout -------------------------------------------------------------

    def _compute_layout(self):
        """Precompute scale, offsets, wall set, and path canvas points."""
        if not self.trajectory:
            return None

        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        if canvas_w <= 1 or canvas_h <= 1:
            return None

        grid_w, grid_h = self.grid_size if self.grid_size else (27, 27)
        tile_w, tile_h = self.tile_size if self.tile_size else (16, 16)

        margin = 15
        available_w = canvas_w - 2 * margin
        available_h = canvas_h - 2 * margin

        scale_x = available_w / grid_w
        scale_y = available_h / grid_h
        scale = min(scale_x, scale_y)

        offset_x = margin + (available_w - grid_w * scale) / 2
        offset_y = margin

        wall_set = {(int(wx), int(wy)) for wx, wy in self.walls}

        path_points = []
        for snapshot in self.trajectory.frame_snapshots:
            for entity in snapshot.entities:
                if entity.entity_id.lower().startswith("delver"):
                    path_points.append(entity.position)
                    break

        canvas_points = []
        for px, py in path_points:
            gx = (px - tile_w / 2) / tile_w
            gy = (grid_h * tile_h - (py - tile_h / 2)) / tile_h
            cx = offset_x + gx * scale
            cy = offset_y + gy * scale
            canvas_points.append((cx, cy))

        max_diag = grid_w + grid_h - 2
        victorious = bool(self.trajectory.victorious)

        return {
            "grid_w": grid_w,
            "grid_h": grid_h,
            "scale": scale,
            "offset_x": offset_x,
            "offset_y": offset_y,
            "wall_set": wall_set,
            "canvas_points": canvas_points,
            "max_diag": max_diag,
            "start_pos": self.start_pos,
            "goal_pos": self.goal_pos,
            "victorious": victorious,
        }

    # --- Drawing primitives -------------------------------------------------

    def _tile_center(self, layout, x, y):
        scale = layout["scale"]
        cx = layout["offset_x"] + (x + 0.5) * scale
        cy = layout["offset_y"] + (y + 0.5) * scale
        return cx, cy, scale / 2

    def _spawn_tile(self, layout, x, y):
        """Create a tile at size 0 (center) and register it for staggered grow."""
        d = x + y
        tag = f"diag_{d}"
        is_wall = (x, y) in layout["wall_set"]
        cx, cy, half = self._tile_center(layout, x, y)

        if is_wall:
            fill, outline = "#4f4f4f", "#3e3e3e"
        else:
            fill, outline = "#171717", "#2a2a2a"

        # Tiny seed rect so the item exists; first grow tick expands it
        item_id = self.canvas.create_rectangle(
            cx,
            cy,
            cx,
            cy,
            outline=outline,
            fill=fill,
            width=1,
            tags=(tag, "tile"),
        )
        self._growing.append(
            {
                "id": item_id,
                "cx": cx,
                "cy": cy,
                "half": half,
                "age": 0,
                "shrinking": False,
            }
        )

    def _draw_diagonal(self, layout, d, grow=False):
        grid_w = layout["grid_w"]
        grid_h = layout["grid_h"]
        for x in range(grid_w):
            y = d - x
            if 0 <= y < grid_h:
                if grow:
                    self._spawn_tile(layout, x, y)
                else:
                    self._draw_tile_full(layout, x, y)

    def _draw_tile_full(self, layout, x, y):
        """Immediate full-size tile (sync redraw path)."""
        d = x + y
        tag = f"diag_{d}"
        cx, cy, half = self._tile_center(layout, x, y)
        is_wall = (x, y) in layout["wall_set"]
        if is_wall:
            fill, outline = "#4f4f4f", "#3e3e3e"
        else:
            fill, outline = "#171717", "#2a2a2a"
        self.canvas.create_rectangle(
            cx - half,
            cy - half,
            cx + half,
            cy + half,
            outline=outline,
            fill=fill,
            width=1,
            tags=(tag, "tile"),
        )

    def _advance_growing(self):
        """Expand or shrink registered tiles by one frame. Returns True if any remain."""
        still = []
        for entry in self._growing:
            age = entry["age"] + 1
            entry["age"] = age

            if entry["shrinking"]:
                # age goes 1..grow_frames; t = 1 → 0
                t = max(0.0, 1.0 - age / self._grow_frames)
            else:
                t = min(1.0, age / self._grow_frames)

            half = entry["half"] * t
            cx, cy = entry["cx"], entry["cy"]
            try:
                self.canvas.coords(
                    entry["id"], cx - half, cy - half, cx + half, cy + half
                )
            except Exception:
                continue

            if entry["shrinking"]:
                if age < self._grow_frames:
                    still.append(entry)
                else:
                    try:
                        self.canvas.delete(entry["id"])
                    except Exception:
                        pass
            else:
                if age < self._grow_frames:
                    still.append(entry)

        self._growing = still
        return bool(still)

    def _draw_goal_marker(self, layout):
        if not layout["goal_pos"]:
            return
        gx, gy = layout["goal_pos"]
        scale = layout["scale"]
        cx = layout["offset_x"] + (gx + 0.5) * scale
        cy = layout["offset_y"] + (gy + 0.5) * scale
        r = max(4.0, scale * 0.4)
        self.canvas.create_oval(
            cx - r,
            cy - r,
            cx + r,
            cy + r,
            fill="#f59e0b",
            outline="#d97706",
            width=2,
            tags=("marker",),
        )
        self.canvas.create_text(
            cx,
            cy,
            text="G",
            fill="#ffffff",
            font=("Arial", int(max(6, scale * 0.5)), "bold"),
            tags=("marker",),
        )

    def _draw_start_marker(self, layout):
        if not layout["start_pos"]:
            return
        sx, sy = layout["start_pos"]
        scale = layout["scale"]
        cx = layout["offset_x"] + (sx + 0.5) * scale
        cy = layout["offset_y"] + (sy + 0.5) * scale
        r = max(4.0, scale * 0.4)
        self.canvas.create_oval(
            cx - r,
            cy - r,
            cx + r,
            cy + r,
            fill="#10b981",
            outline="#059669",
            width=2,
            tags=("marker",),
        )
        self.canvas.create_text(
            cx,
            cy,
            text="S",
            fill="#ffffff",
            font=("Arial", int(max(6, scale * 0.5)), "bold"),
            tags=("marker",),
        )

    def _draw_end_marker(self, layout):
        canvas_points = layout["canvas_points"]
        if not canvas_points:
            return
        ex, ey = canvas_points[-1]
        scale = layout["scale"]
        r = max(5.0, scale * 0.4)
        end_color = "#10b981" if layout["victorious"] else "#ef4444"
        self.canvas.create_oval(
            ex - r,
            ey - r,
            ex + r,
            ey + r,
            fill=end_color,
            outline="#ffffff",
            width=2,
            tags=("marker",),
        )
        marker_text = "🏆" if layout["victorious"] else "💀"
        self.canvas.create_text(
            ex,
            ey,
            text=marker_text,
            font=("Arial", int(max(7, scale * 0.5))),
            tags=("marker",),
        )

    def _draw_path_batch(self, layout, start_idx, batch_size):
        points = layout["canvas_points"]
        if len(points) < 2:
            return 0

        end_idx = min(start_idx + batch_size, len(points) - 1)
        if end_idx <= start_idx:
            return 0

        coords = []
        for i in range(start_idx, end_idx + 1):
            coords.extend(points[i])

        self.canvas.create_line(
            *coords,
            fill="#3b82f6",
            width=3,
            tags=("path",),
        )
        return end_idx - start_idx

    def _draw_full(self, layout):
        """Synchronous full draw of grid, walls, markers, and path."""
        max_diag = layout["max_diag"]
        for d in range(max_diag + 1):
            self._draw_diagonal(layout, d, grow=False)

        self._draw_goal_marker(layout)
        self._draw_start_marker(layout)

        points = layout["canvas_points"]
        if len(points) > 1:
            coords = []
            for p in points:
                coords.extend(p)
            self.canvas.create_line(
                *coords,
                fill="#3b82f6",
                width=3,
                tags=("path",),
            )

        self._draw_end_marker(layout)

    # --- Reveal animation ---------------------------------------------------

    def _start_reveal(self):
        """Animate tiles + path in parallel (new / different level)."""
        layout = self._compute_layout()
        if layout is None:
            self._layout = None
            return

        self._layout = layout
        self._has_drawn_content = True
        self._tiles_complete = False
        self._growing = []

        self._draw_goal_marker(layout)
        self._draw_start_marker(layout)

        num_diags = layout["max_diag"] + 1
        self._diags_per_tick = self._items_per_tick(
            num_diags, self._tile_reveal_ms, self._tick_ms
        )
        self._tile_next_d = 0
        self._tiles_done = False

        self._prepare_path_anim(layout)
        self._schedule_tick()

    def _start_path_only(self):
        """Animate path only (same level as previous trajectory)."""
        layout = self._compute_layout()
        if layout is None:
            self._layout = None
            return

        self._layout = layout
        self._has_drawn_content = True
        self._tiles_done = True
        self._growing = []

        self._draw_goal_marker(layout)
        self._draw_start_marker(layout)
        self._prepare_path_anim(layout)

        if self._path_done:
            self._anim_after_id = None
            return
        self._schedule_tick()

    def _prepare_path_anim(self, layout):
        points = layout["canvas_points"]
        segments = max(0, len(points) - 1)
        if segments == 0:
            self._path_done = True
            self._draw_end_marker(layout)
            return

        self._path_batch = self._items_per_tick(
            segments, self._path_reveal_ms, self._tick_ms
        )
        self._path_idx = 0
        self._path_done = False

    def _anim_tick(self, gen):
        if gen != self._anim_gen:
            return

        layout = self._layout
        if layout is None:
            self._anim_after_id = None
            return

        if not self._tiles_done:
            self._advance_tile_reveal(layout)

        if not self._path_done:
            self._advance_path_reveal(layout)

        # Keep path/markers above tiles as diagonals keep spawning
        self.canvas.tag_raise("path")
        self.canvas.tag_raise("marker")

        if gen != self._anim_gen:
            return

        if not self._tiles_done or not self._path_done:
            self._schedule_tick()
        else:
            self._anim_after_id = None

    def _advance_tile_reveal(self, layout):
        max_diag = layout["max_diag"]
        next_d = self._tile_next_d

        if next_d <= max_diag:
            end_d = min(next_d + self._diags_per_tick - 1, max_diag)
            for d in range(next_d, end_d + 1):
                self._draw_diagonal(layout, d, grow=True)
            self._tile_next_d = end_d + 1

        still_growing = self._advance_growing()
        if self._tile_next_d > max_diag and not still_growing:
            self._tiles_done = True
            self._tiles_complete = True

    def _advance_path_reveal(self, layout):
        points = layout["canvas_points"]
        if len(points) < 2:
            self._path_done = True
            self._draw_end_marker(layout)
            return

        drawn = self._draw_path_batch(layout, self._path_idx, self._path_batch)
        if drawn <= 0:
            # Avoid infinite ticks if batch can't advance (bad indices / empty)
            self._path_done = True
            self._draw_end_marker(layout)
            return

        self._path_idx += drawn

        if self._path_idx >= len(points) - 1:
            self._path_done = True
            self._draw_end_marker(layout)

    # --- Wipe animation -----------------------------------------------------

    def _start_wipe(self):
        layout = self._layout
        if layout is None:
            self._finish_wipe()
            return

        self.canvas.delete("path")
        self.canvas.delete("marker")
        self._growing = []
        self._tiles_done = False
        self._path_done = True
        self._tiles_complete = False

        max_diag = layout["max_diag"]
        diags_per_tick = self._items_per_tick(
            max_diag + 1, self._tile_wipe_ms, self._tick_ms
        )
        gen = self._anim_gen
        self._wipe_step(max_diag, diags_per_tick, gen)

    def _queue_diag_shrink(self, layout, d):
        """Register tiles on diagonal d for shrink-out (reuse canvas items)."""
        for item_id in self.canvas.find_withtag(f"diag_{d}"):
            tags = self.canvas.gettags(item_id)
            if "tile" not in tags:
                continue
            coords = self.canvas.coords(item_id)
            if len(coords) < 4:
                continue
            x1, y1, x2, y2 = coords[:4]
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2
            half = layout["scale"] / 2
            self._growing.append(
                {
                    "id": item_id,
                    "cx": cx,
                    "cy": cy,
                    "half": half,
                    "age": 0,
                    "shrinking": True,
                }
            )

    def _wipe_step(self, next_d, diags_per_tick, gen):
        if gen != self._anim_gen:
            return

        layout = self._layout
        if layout is None:
            self._finish_wipe()
            return

        end_d = max(next_d - diags_per_tick + 1, 0)
        for d in range(next_d, end_d - 1, -1):
            self._queue_diag_shrink(layout, d)

        still_growing = self._advance_growing()
        wiped_all = end_d <= 0

        if gen != self._anim_gen:
            return

        if not wiped_all or still_growing:
            self._anim_after_id = self.after(
                self._tick_ms,
                lambda: self._wipe_step(
                    end_d - 1 if not wiped_all else -1,
                    diags_per_tick,
                    gen,
                ),
            )
        else:
            self._finish_wipe()

    def _finish_wipe(self):
        self._anim_after_id = None
        self.canvas.delete("all")
        self._clear_state()
        self._has_drawn_content = False
        self._tiles_complete = False
