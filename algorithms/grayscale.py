"""5. Grayscale - luminance conversion with cv2.cvtColor()."""
from ._utils import to_gray

INFO = {
    "id": "grayscale",
    "name": "Grayscale",
    "summary": "Converts colour to a single luminance channel weighted to human perception.",
    "formula": "Y = 0.299 R + 0.587 G + 0.114 B",
    "params": [],
}


def apply(img, params):
    # The pipeline keeps images in BGR order, so COLOR_BGR2GRAY is the correct code here.
    return to_gray(img)
