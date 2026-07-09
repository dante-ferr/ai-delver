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

        temp_svg_path = self._edit_svg(svg_path, stroke, fill)

        png_data = cairosvg.svg2png(
            url=temp_svg_path, output_width=self.size[0], output_height=self.size[1]
        )
        if type(png_data) != bytes:
            raise RuntimeError("Failed to convert SVG to PNG")

        os.remove(temp_svg_path)

        return Image.open(BytesIO(png_data))

    def _edit_svg(self, svg_path: str, stroke: str, fill: str):
        with open(svg_path, "r") as file:
            svg_content = file.read()

        svg_content = re.sub(r'stroke="[^"]+"', f'stroke="{stroke}"', svg_content)
        svg_content = re.sub(r'fill="[^"]+"', f'fill="{fill}"', svg_content)

        temp_svg_path = temp_svg_path = os.path.join(
            os.getenv("TEMP_DIR", "/tmp"), "temp_modified.svg"
        )
        with open(temp_svg_path, "w") as temp_file:
            temp_file.write(svg_content)

        return temp_svg_path

    def get_ctk_image(self):
        ctk_image = ctk.CTkImage(light_image=self.image, size=self.size)
        return ctk_image

    def get_tk_image(self):
        tk_image = ImageTk.PhotoImage(image=self.image)
        return tk_image
