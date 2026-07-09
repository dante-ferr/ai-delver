from PIL import Image
from .get_average_color import get_average_color


def get_average_color_from_raw_data(
    data: bytes,
    size: tuple[int, int],
    mode: str,
) -> tuple[int, int, int] | None:
    """
    Creates an image from raw pixel data and calculates its average color.

    Args:
        mode: The color mode of the raw data (e.g., 'RGB', 'RGBA').
        size: The (width, height) of the image.
        data: The raw pixel data as bytes.

    Returns:
        A tuple representing the average RGB color (r, g, b), or None on error.
    """
    if not data:
        return None
    try:
        img = Image.frombytes(mode, size, data)
        return get_average_color(img)
    except (ValueError, IndexError) as e:
        print(f"Error creating image from raw data: {e}")
        return None
