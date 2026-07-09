from PIL import Image
import io
from .get_average_color import get_average_color


def get_average_color_from_bytes(image_bytes: bytes) -> tuple[int, int, int] | None:
    """
    Calculates the average color of an image provided in a standard
    file format (like PNG, JPEG) as bytes.

    Args:
        image_bytes: The image content in bytes format.

    Returns:
        A tuple representing the average RGB color (r, g, b),
        or None if the image data is invalid.
    """
    if not image_bytes:
        return None

    try:
        img = Image.open(io.BytesIO(image_bytes))
        return get_average_color(img)

    except (IOError, SyntaxError) as e:
        print(f"Error processing image bytes: {e}")
        return None
