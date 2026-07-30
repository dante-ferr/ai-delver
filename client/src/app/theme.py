import json
import customtkinter as ctk
from src.config import config


class Theme:
    def __init__(self, theme_name: str):
        self.name = theme_name
        self.load(theme_name)

    def load(self, theme_name: str):
        self.name = theme_name
        self.path = config.ASSETS_PATH / "themes" / f"{theme_name}.json"

        with open(self.path, "r") as file:
            data = json.load(file)

        self.data = data
        self.display_name = data.get("_comments", {}).get(
            "Theme", theme_name.replace("_", " ").title()
        )
        custom = data.get("custom", {})

        # Color Groups
        self.neutral = custom.get("neutral", {})
        self.primary_group = custom.get("primary", {})
        self.secondary_group = custom.get("secondary", {})
        self.special = custom.get("special", ["#cbaa89", "#bf7f3f", "#73573b", "#5f3214", "#401811"])

        # Backgrounds & Surface Gradients (Neutral Group)
        self.bg_darkest = self.neutral.get("darkest", "#050608")
        self.bg_dark = self.neutral.get("dark", "#0d0f12")
        self.bg_mid = self.neutral.get("mid", "#16191e")
        self.bg_dark_mid = self.neutral.get("dark_mid", self.bg_dark)
        self.bg_mid_light = self.neutral.get("mid_light", self.bg_mid)

        # Wall Tones (Minimap / Path Visualizer)
        self.wall_fill = self.neutral.get("wall_fill", "#1c2f4c")
        self.wall_outline = self.neutral.get("wall_outline", "#3a5b88")

        # Text Tones
        self.text_light = self.neutral.get("light", "#e2e8f0")
        self.text_slate = self.neutral.get("slate", "#94a3b8")

        # Primary Group (Ramp)
        self.primary_color = self.primary_group.get("main", custom.get("primary_color", "#00ffff"))
        self.primary_lighter = self.primary_group.get("lighter", custom.get("primary_lighter", "#66ffff"))
        self.primary_darker = self.primary_group.get("dark", custom.get("primary_darker", "#0f377d"))
        self.primary_darkest = self.primary_group.get("darkest", custom.get("primary_darkest", "#162c52"))

        # Secondary Group (Ramp)
        self.secondary_color = self.secondary_group.get("main", custom.get("secondary_color", "#573b73"))
        self.secondary_dark = self.secondary_group.get("dark", custom.get("secondary_dark", "#463246"))
        self.secondary_darkest = self.secondary_group.get("darkest", custom.get("secondary_darkest", "#3c233c"))

        self.select_border_color = custom.get("select_border_color", self.primary_color)
        self.icon_color = data.get("CTkLabel", {}).get("text_color", ["gray10", "#999999"])[1]

        try:
            ctk.set_default_color_theme(str(self.path))
        except Exception:
            pass


def list_available_themes() -> list[str]:
    themes_dir = config.ASSETS_PATH / "themes"
    if not themes_dir.exists():
        return ["dungeon"]
    return sorted([f.stem for f in themes_dir.glob("*.json")])


def theme_display_name(theme_name: str) -> str:
    path = config.ASSETS_PATH / "themes" / f"{theme_name}.json"
    try:
        with open(path, "r") as file:
            data = json.load(file)
        return data.get("_comments", {}).get(
            "Theme", theme_name.replace("_", " ").title()
        )
    except (OSError, json.JSONDecodeError):
        return theme_name.replace("_", " ").title()


def theme_stem_from_display_name(display_name: str) -> str | None:
    for stem in list_available_themes():
        if theme_display_name(stem) == display_name:
            return stem
    return None


default_theme = "dungeon"
theme = Theme(default_theme)
