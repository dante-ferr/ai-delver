import numpy as np
import matplotlib.pyplot as plt


def plot_bytes_image(image_bytes, width, height):
    # Convert byte data to a NumPy array
    img_array = np.frombuffer(image_bytes, dtype=np.uint8)
    img_array = img_array.reshape((height, width, 4))  # Assuming RGBA format

    # Display the image using matplotlib
    plt.imshow(img_array)
    plt.axis("off")  # Optional: Hide axis
    plt.show()
