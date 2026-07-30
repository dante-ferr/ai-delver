import cairosvg
from PIL import Image, ImageTk
from io import BytesIO
from pathlib import Path
import os
import re
import customtkinter as ctk

class SvgImage(ImageTk.PhotoImage):
    def __init__(
        self,
        svg_path: str,
        stroke: str = "#000000",
        fill: str = "none",
        size: tuple[int, int] = (32, 32),
    ):
        self.size = size
        self.image = self._get_bytes_image(svg_path, stroke, fill)

    def _get_bytes_image(self, svg_path: str, stroke: str, fill: str):
        path = Path(svg_path)
        if not path.exists():
            raise FileNotFoundError(f"SVG file not found: {svg_path}")

        with open(svg_path, "r", encoding="utf-8") as file:
            svg_content = file.read()

        svg_content = re.sub(r'stroke="[^"]+"', f'stroke="{stroke}"', svg_content)
        svg_content = re.sub(r'fill="[^"]+"', f'fill="{fill}"', svg_content)

        png_data = cairosvg.svg2png(
            bytestring=svg_content.encode("utf-8"),
            output_width=self.size[0],
            output_height=self.size[1],
        )
        if type(png_data) != bytes:
            raise RuntimeError("Failed to convert SVG to PNG")

        return Image.open(BytesIO(png_data))

    def get_ctk_image(self):
        ctk_image = ctk.CTkImage(light_image=self.image, size=self.size)
        return ctk_image

    def get_tk_image(self):
        tk_image = ImageTk.PhotoImage(image=self.image)
        return tk_image
