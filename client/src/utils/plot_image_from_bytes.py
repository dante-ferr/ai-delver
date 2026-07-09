import matplotlib.pyplot as plt
from PIL import Image
from io import BytesIO


def plot_image_from_bytes(image_bytes: bytes):
    image = Image.open(BytesIO(image_bytes))
    plt.imshow(image)
    plt.axis("off")
    plt.show()
