import sys
import customtkinter as ctk
from PIL import Image, ImageSequence
from pathlib import Path
from src.config import config


class AnimatedGifLabel(ctk.CTkLabel):
    """
    A CustomTkinter label that plays an animated GIF.
    If the requested GIF does not exist in the assets directory,
    it automatically exports it using pyglet-dragonbones' export_animation_gif.
    """
    def __init__(self, master, **kwargs):
        super().__init__(master, text="", **kwargs)
        self.frames = []
        self.durations = []
        self.current_frame_idx = 0
        self.after_id = None
        self._current_gif_path = None

    def load_gif_by_name(self, animation_name: str, target_height: int | None = None):
        """
        Loads a GIF by animation name ('idle' or 'run').
        If the GIF is not found, it is automatically generated.
        """
        if target_height is None:
            target_height = int(config.DELVER_GIF.TARGET_HEIGHT)

        gif_dir = config.ASSETS_PATH / "img" / "sprites" / "delver"
        gif_path = gif_dir / f"delver_{animation_name}.gif"
        
        # Fallback generator if not present
        if not gif_path.exists():
            try:
                # Add pyglet-dragonbones-lib to sys.path if not already present
                lib_path = config.PROJECT_ROOT / "pyglet-dragonbones-lib"
                if str(lib_path) not in sys.path:
                    sys.path.insert(0, str(lib_path))
                
                from pyglet_dragonbones.utils.export_animation_gif import export_animation_gif
                skeleton_path = config.ASSETS_PATH / "img" / "sprites" / "delver"
                # Ensure the folder exists
                gif_path.parent.mkdir(parents=True, exist_ok=True)
                export_animation_gif(
                    skeleton_path,
                    animation_name,
                    gif_path,
                    scale=float(config.DELVER_GIF.SCALE),
                    antialias=bool(config.DELVER_GIF.ANTIALIAS),
                )
            except Exception as e:
                print(f"[AnimatedGifLabel Error] Failed to export GIF '{animation_name}': {e}")
                # We don't raise/crash, we just return so we don't block the UI
                return

        if self._current_gif_path == gif_path:
            return  # Already playing this GIF
            
        self.stop()
        self._current_gif_path = gif_path
        
        try:
            im = Image.open(gif_path)
            self.frames = []
            self.durations = []
            width, height = im.size
            
            # Scale dynamically preserving aspect ratio
            scale_factor = target_height / height
            target_width = int(round(width * scale_factor))
            
            for frame in ImageSequence.Iterator(im):
                frame_copy = frame.copy().convert("RGBA")
                ctk_img = ctk.CTkImage(light_image=frame_copy, dark_image=frame_copy, size=(target_width, target_height))
                self.frames.append(ctk_img)
                self.durations.append(frame.info.get("duration", 100))
                
            self.current_frame_idx = 0
            if self.frames:
                self._update_frame()
        except Exception as e:
            print(f"[AnimatedGifLabel Error] Failed to load GIF '{gif_path}': {e}")

    def _update_frame(self):
        if not self.winfo_exists():
            return
        if not self.frames:
            return
        
        img = self.frames[self.current_frame_idx]
        self.configure(image=img)
        
        duration = self.durations[self.current_frame_idx]
        self.current_frame_idx = (self.current_frame_idx + 1) % len(self.frames)
        
        self.after_id = self.after(duration, self._update_frame)

    def stop(self):
        if self.after_id is not None:
            self.after_cancel(self.after_id)
            self.after_id = None
        self.frames = []
        self.durations = []
        self._current_gif_path = None

    def destroy(self):
        self.stop()
        super().destroy()
