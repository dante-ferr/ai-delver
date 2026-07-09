import math


def angle_to_vector(angle, degrees=True):
    """Converts an angle to a 2D unit vector.

    Args:
        angle (float): The angle to convert.
        degrees (bool): If True, angle is in degrees. If False, it's in radians.

    Returns:
        tuple: (x, y) unit vector
    """
    if degrees:
        angle = math.radians(angle)

    return (math.cos(angle), math.sin(angle))
