import math
from typing import Sequence


def vector_to_angle(vector: Sequence[float]) -> float:
    """Converts a 2D vector to an angle in degrees (0-360)."""
    x, y = vector
    angle_radians = math.atan2(y, x)
    angle_degrees = math.degrees(angle_radians)

    # Ensure the angle is in the range [0, 360)
    return (angle_degrees + 360) % 360
