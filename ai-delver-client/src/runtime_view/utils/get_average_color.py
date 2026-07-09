from PIL import Image

def get_average_color(image_object: Image.Image) -> tuple[int, int, int]:
    """
    Calculates the average color of a PIL Image object.
    This is the most efficient method if you already have an Image object.

    Args:
        image_object: A PIL.Image.Image object.

    Returns:
        A tuple representing the average RGB color (r, g, b).
    """
    # Ensure the image is in RGB format for consistency
    img = image_object.convert('RGB')
    
    # Get the total number of pixels
    width, height = img.size
    num_pixels = width * height
    
    if num_pixels == 0:
        return (0, 0, 0)

    # Get a list of all pixel values
    pixels = list(img.getdata())
    
    # Initialize sums for each color channel
    total_r, total_g, total_b = 0, 0, 0
    
    # Calculate the sum of each color channel
    for r, g, b in pixels:
        total_r += r
        total_g += g
        total_b += b
        
    # Calculate the average for each channel
    avg_r = total_r // num_pixels
    avg_g = total_g // num_pixels
    avg_b = total_b // num_pixels
    
    return (avg_r, avg_g, avg_b)