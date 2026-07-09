from src.config import config
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from runtime.world_objects import WorldObject
    from pyglet.window import Window


class Camera:
    """
    A 2D camera for the pyglet window that handles zooming, panning, and following objects.

    This camera uses a context manager (`with camera:`) to apply its transformations
    to the window's view matrix. It supports smooth zooming and smooth following of a
    target `WorldObject`. The transformations are calculated to keep the camera's
    focal point at the center of the screen.
    """

    offset_x: float = 0
    offset_y: float = 0

    world_object_being_followed: Optional["WorldObject"] = None
    follow_smoothing_factor = 0.05

    _zoom_target: float = 1.0
    _zoom: float = 1.0
    zoom_smoothing_factor: float = 0.1

    _original_view = None

    def __init__(
        self,
        window: "Window",
        start_zoom=config.CAMERA.START_ZOOM,
        min_zoom=config.CAMERA.MIN_ZOOM,
        max_zoom=config.CAMERA.MAX_ZOOM,
        scroll_speed=config.CAMERA.SCROLL_SPEED,
        zoom_speed=config.CAMERA.ZOOM_SPEED,
    ):
        assert (
            min_zoom <= max_zoom
        ), "Minimum zoom must not be greater than maximum zoom"
        self._window = window
        self.scroll_speed = scroll_speed

        self.max_zoom = max_zoom
        self.min_zoom = min_zoom

        self.zoom_speed = zoom_speed

        # Set the initial zoom without smoothing.
        self.immediate_zoom(start_zoom)

    def immediate_zoom(self, value: float):
        """Set the zoom value immediately."""
        clamped_value = self._clamp_zoom(value)
        self._zoom_target = clamped_value
        self._zoom = clamped_value

    def scroll_zoom(self, scroll_y):
        self.zoom = self.zoom + scroll_y * self.zoom_speed

    @property
    def zoom(self):
        """Get the current zoom target value."""
        return self._zoom_target

    @zoom.setter
    def zoom(self, value):
        """Set the zoom target, clamping the value."""
        self._zoom_target = self._clamp_zoom(value)

    def _clamp_zoom(self, value: float):
        """Clamp zoom value to min and max zoom."""
        return max(min(value, self.max_zoom), self.min_zoom)

    @property
    def position(self):
        """Query the current offset."""
        return self.offset_x, self.offset_y

    @position.setter
    def position(self, value):
        """Set the scroll offset directly."""
        self.offset_x, self.offset_y = value

    def move(self, axis_x, axis_y):
        """Move the camera by a given amount."""
        self.offset_x += self.scroll_speed * axis_x
        self.offset_y += self.scroll_speed * axis_y

    def start_following(self, world_object: "WorldObject"):
        """Start following a given world object."""
        self.world_object_being_followed = world_object
        # Immediately set the camera's position to the object's position
        self.position = self.world_object_being_followed.position

    def __enter__(self):
        self.begin()

    def __exit__(self, exception_type, exception_value, traceback):
        self.end()

    def begin(self):
        """Saves the current view and applies camera transformations."""
        # Save the original, clean view matrix
        self._original_view = self._window.view

        # Update camera logic (smoothing, following, etc.)
        self._follow_world_object()
        self._smooth_zoom()

        # Apply the actual transformation for drawing
        self._apply_view_matrix_transformation()

    def end(self):
        """Restores the original, clean view matrix."""
        if self._original_view:
            self._window.view = self._original_view

    def translate_mouse_coords(self, coords: tuple[float, float]):
        """Converts window coordinates to world coordinates."""
        from pyglet.math import Vec3

        x, y = coords  # type: ignore
        # Invert the view matrix to go from screen->world
        inv_matrix = self._window.view.inverse()
        world_x, world_y, _ = inv_matrix @ Vec3(x, y, 0)
        return world_x, world_y

    def _apply_view_matrix_transformation(self):
        """
        Builds the camera's view matrix from scratch each frame.
        This is robust and avoids cumulative errors.
        The transformations are applied in reverse order of how you'd think about them.
        """
        from pyglet.math import Vec3

        view_matrix = self._original_view
        if not view_matrix:
            return

        # 3. Move the origin to the center of the screen.
        view_matrix = view_matrix.translate(
            Vec3(self._window.width / 2, self._window.height / 2, 0)
        )

        # 2. Scale (zoom) around the new origin (the screen center).
        view_matrix = view_matrix.scale(Vec3(self._zoom, self._zoom, 1))

        # 1. Move the world so that the camera's target position (offset_x, offset_y)
        # is at the origin before scaling and translating.
        view_matrix = view_matrix.translate(Vec3(-self.offset_x, -self.offset_y, 0))

        self._window.view = view_matrix

    def _smooth_zoom(self):
        """Smoothly interpolates the current zoom level towards the target zoom."""
        if abs(self._zoom_target - self._zoom) > 0.001:
            self._zoom += (self._zoom_target - self._zoom) * self.zoom_smoothing_factor

    def _follow_world_object(self):
        """Smoothly moves the camera towards the object it's following."""
        if not self.world_object_being_followed:
            return

        # Calculate the distance to the target object.
        dx, dy = (
            self.distance_to_world_object[0],
            self.distance_to_world_object[1],
        )

        # Move the camera towards the target
        self.offset_x += dx * self.follow_smoothing_factor
        self.offset_y += dy * self.follow_smoothing_factor

    @property
    def distance_to_world_object(self):
        """The vector from the camera's current position to the followed object."""
        if not self.world_object_being_followed:
            return (0.0, 0.0)
        return (
            self.world_object_position[0] - self.offset_x,
            self.world_object_position[1] - self.offset_y,
        )

    @property
    def world_object_position(self):
        """The position of the object being followed."""
        if not self.world_object_being_followed:
            return (0.0, 0.0)
        return (
            self.world_object_being_followed.position[0],
            self.world_object_being_followed.position[1],
        )
