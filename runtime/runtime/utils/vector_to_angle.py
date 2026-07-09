import math


def vector_to_angle(vector):
    x, y = vector
    angle_radians = math.atan2(y, x)
    angle_degrees = math.degrees(angle_radians)
    return angle_degrees
