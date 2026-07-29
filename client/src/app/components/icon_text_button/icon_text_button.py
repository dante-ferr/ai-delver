import customtkinter as ctk
import tkinter.font as tkfont
from app.fonts import app_font
from app.theme import theme
from app.components.svg_image.svg_image import SvgImage
from src.config import config


class IconTextButton(ctk.CTkButton):
    """
    A CustomTkinter button that supports an SVG icon displayed before the text (compound='left').
    Automatically hides/unpacks the icon if there is insufficient horizontal space to display the text.
    """

    def __init__(
        self,
        master,
        svg_path: str | None = None,
        icon_size: tuple[int, int] = (16, 16),
        **kwargs,
    ):
        kwargs.setdefault("cursor", "hand2")
        if "font" not in kwargs:
            kwargs["font"] = app_font(
                size=config.STYLE.FONT.STANDARD_SIZE, weight="bold"
            )
        kwargs.setdefault("height", 32)

        self._svg_path = svg_path
        self._icon_size = icon_size
        self._icon_image: ctk.CTkImage | None = None
        self._is_icon_packed: bool = False
        self._btn_text: str = kwargs.get("text", "")

        if svg_path:
            try:
                svg_img = SvgImage(
                    svg_path=svg_path,
                    size=icon_size,
                    fill=theme.icon_color,
                    stroke=theme.icon_color,
                )
                self._icon_image = svg_img.get_ctk_image()
                kwargs["image"] = self._icon_image
                kwargs.setdefault("compound", "left")
                self._is_icon_packed = True
            except Exception as e:
                print(f"[IconTextButton Error] Failed to load SVG '{svg_path}': {e}")
                self._icon_image = None

        super().__init__(master, **kwargs)

        self._idle_after_id: str | None = None

        if self._icon_image is not None and self._btn_text:
            self.bind("<Configure>", self._on_configure, add="+")
            if self.master:
                try:
                    self.master.bind("<Configure>", self._on_configure, add="+")
                except Exception:
                    pass
            self._schedule_check()

    def configure(self, require_redraw=False, **kwargs):
        if "text" in kwargs:
            self._btn_text = kwargs["text"]
        if "svg_path" in kwargs:
            self._svg_path = kwargs.pop("svg_path")
            if self._svg_path:
                try:
                    svg_img = SvgImage(
                        svg_path=self._svg_path,
                        size=self._icon_size,
                        fill=theme.icon_color,
                        stroke=theme.icon_color,
                    )
                    self._icon_image = svg_img.get_ctk_image()
                    kwargs["image"] = self._icon_image
                    self._is_icon_packed = True
                except Exception:
                    self._icon_image = None
            else:
                self._icon_image = None
                kwargs["image"] = None
        super().configure(require_redraw=require_redraw, **kwargs)
        if self._icon_image is not None and self._btn_text:
            self._schedule_check()

    def _on_configure(self, event=None):
        self._schedule_check()

    def _schedule_check(self):
        if self._idle_after_id is not None:
            self.after_cancel(self._idle_after_id)
        self._idle_after_id = self.after_idle(self._check_responsive)

    def _get_available_width(self) -> int:
        w = self.winfo_width()
        if w > 1:
            return w
        if self.master and hasattr(self.master, "winfo_width"):
            mw = self.master.winfo_width()
            if mw > 1:
                cols = 1
                try:
                    info = self.grid_info()
                    if info:
                        grid_size = self.master.grid_size()
                        cols = max(1, grid_size[0])
                except Exception:
                    pass
                cell_w = (mw / cols) - 8
                if w <= 1 or cell_w < w:
                    w = cell_w
        return int(w)

    def _calculate_required_width(self) -> int:
        if not self._btn_text:
            return 0
        font_obj = self.cget("font")
        try:
            if hasattr(font_obj, "measure"):
                text_width = font_obj.measure(self._btn_text)
            elif isinstance(font_obj, tuple):
                family = font_obj[0]
                size = font_obj[1]
                weight = font_obj[2] if len(font_obj) > 2 else "normal"
                f = tkfont.Font(family=family, size=size, weight=weight)
                text_width = f.measure(self._btn_text)
            else:
                f = tkfont.Font(size=config.STYLE.FONT.STANDARD_SIZE, weight="bold")
                text_width = f.measure(self._btn_text)
        except Exception:
            text_width = len(self._btn_text) * 7

        icon_w = self._icon_size[0] if self._icon_image else 0
        return text_width + icon_w + 14

    def _check_responsive(self):
        self._idle_after_id = None
        if self._icon_image is None or not self._btn_text:
            return
        avail_w = self._get_available_width()
        if avail_w <= 1:
            return

        req_width = self._calculate_required_width()

        if avail_w < req_width:
            if self._is_icon_packed:
                super().configure(image=None)
                self._is_icon_packed = False
        else:
            if not self._is_icon_packed:
                if self._icon_image is not None:
                    if hasattr(self._icon_image, "_scaled_light_photo_images"):
                        self._icon_image._scaled_light_photo_images.clear()
                    if hasattr(self._icon_image, "_scaled_dark_photo_images"):
                        self._icon_image._scaled_dark_photo_images.clear()
                super().configure(image=self._icon_image, require_redraw=True)
                self._is_icon_packed = True
