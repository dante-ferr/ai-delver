import customtkinter as ctk
from app.fonts import canvas_font


class StatsMiniGraph(ctk.CTkCanvas):
    """
    A custom, high-performance canvas-based mini graph to plot trajectory
    metrics (like victories or step counts) inline without using matplotlib.
    """
    def __init__(self, master, title: str, line_color: str, empty_text: str = "No data", **kwargs):
        # Resolve a real single Tk color for the canvas bg.
        # CTk's fg_color can be:
        #   - A (light, dark) tuple
        #   - A space-separated "light dark" string (Toplevel/App quirk)
        #   - "transparent" (must walk up to find a real color)
        #   - A plain hex string
        bg_color = self._resolve_bg_color(master)

        super().__init__(
            master,
            bg=bg_color,
            highlightthickness=0,
            **kwargs
        )
        self.title = title
        self.line_color = line_color
        self.empty_text = empty_text
        self.data = []
        self.bind("<Configure>", lambda e: self.redraw())

    @staticmethod
    def _resolve_bg_color(widget, fallback: str = "#2b2b2b") -> str:
        """
        Walks up the widget tree to resolve a real Tk-compatible background color.
        Handles CTk's internal (light, dark) tuple, space-separated strings, and
        'transparent' by climbing to the nearest ancestor with a concrete color.
        """
        mode_index = 0 if ctk.get_appearance_mode() == "Light" else 1

        current = widget
        while current is not None:
            try:
                raw = current.cget("fg_color")
            except Exception:
                break

            # Tuple form: ("light_color", "dark_color")
            if isinstance(raw, (list, tuple)) and len(raw) == 2:
                color = raw[mode_index]
            elif isinstance(raw, str) and " " in raw:
                parts = raw.split()
                color = parts[min(mode_index, len(parts) - 1)]
            else:
                color = raw

            if color and color != "transparent":
                return color

            # Climb one level
            try:
                current = current.master
            except AttributeError:
                break

        return fallback

    def set_data(self, data: list):
        self.data = data
        self.redraw()

    def redraw(self):
        self.delete("all")

        width = self.winfo_width()
        height = self.winfo_height()

        if width <= 1 or height <= 1:
            return

        # Margins
        margin_left = 35
        margin_right = 10
        margin_top = 22
        margin_bottom = 20

        plot_w = width - margin_left - margin_right
        plot_h = height - margin_top - margin_bottom

        # Draw title
        self.create_text(
            width / 2, 8,
            text=self.title,
            fill="#ffffff",
            font=canvas_font(9, bold=True)
        )

        # Draw axes
        self.create_line(
            margin_left, margin_top,
            margin_left, height - margin_bottom,
            fill="#555555", width=1
        )
        self.create_line(
            margin_left, height - margin_bottom,
            width - margin_right, height - margin_bottom,
            fill="#555555", width=1
        )

        if not self.data:
            self.create_text(
                width / 2, height / 2,
                text=self.empty_text,
                fill="#888888",
                font=canvas_font(9)
            )
            return

        n = len(self.data)
        max_val = max(self.data)
        min_val = min(self.data)

        # Avoid division by zero
        val_range = max_val - min_val
        if val_range == 0:
            val_range = 1
            min_val = max(0.0, min_val - 0.5)

        # Draw grid & Y labels (min, middle, max)
        for i in range(3):
            ratio = i / 2.0
            y = height - margin_bottom - ratio * plot_h
            val = min_val + ratio * (max_val - min_val)

            # Grid line
            self.create_line(
                margin_left, y,
                width - margin_right, y,
                fill="#3a3a3a", dash=(2, 2)
            )

            # Label
            val_str = f"{int(val)}" if val.is_integer() else f"{val:.1f}"
            if val > 1000:
                val_str = f"{val/1000:.1f}k"
            self.create_text(
                margin_left - 5, y,
                text=val_str,
                anchor="e",
                fill="#aaaaaa",
                font=canvas_font(7)
            )

        # Draw X labels (first and last index)
        self.create_text(
            margin_left, height - margin_bottom + 4,
            text="1",
            anchor="n",
            fill="#aaaaaa",
            font=canvas_font(7)
        )
        self.create_text(
            width - margin_right, height - margin_bottom + 4,
            text=str(n),
            anchor="n",
            fill="#aaaaaa",
            font=canvas_font(7)
        )

        # Draw data line
        points = []
        for idx, val in enumerate(self.data):
            x = margin_left + (idx / max(1, n - 1)) * plot_w
            y = height - margin_bottom - ((val - min_val) / val_range) * plot_h
            points.append((x, y))

        # Draw lines connecting points
        for idx in range(len(points) - 1):
            p1 = points[idx]
            p2 = points[idx+1]
            self.create_line(
                p1[0], p1[1],
                p2[0], p2[1],
                fill=self.line_color,
                width=2
            )
