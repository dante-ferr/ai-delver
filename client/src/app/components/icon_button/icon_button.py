import customtkinter as ctk
from ..svg_image.svg_image import SvgImage
from app.theme import theme


class IconButton(ctk.CTkButton):

    def __init__(self, master, svg_path: str, **kwargs):

        icon = SvgImage(
            svg_path=svg_path,
            size=(kwargs.get("width", 20), kwargs.get("height", 20)),
            fill=theme.icon_color,
            stroke=theme.icon_color,
        )

        if kwargs.get("text"):
            raise ValueError("IconButton cannot have text")
        if kwargs.get("image"):
            raise ValueError("IconButton cannot have image")

        kwargs.setdefault("fg_color", "transparent")
        kwargs.setdefault("width", 24)
        kwargs.setdefault("height", 24)
        kwargs.setdefault("hover_color", "#555")

        super().__init__(master, text="", image=icon.get_ctk_image(), **kwargs)
