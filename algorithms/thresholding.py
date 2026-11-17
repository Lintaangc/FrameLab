"""1. Thresholding - grayscale -> binary image with cv2.threshold()."""
import cv2

from ._utils import get_number, to_gray

INFO = {
    "id": "thresholding",
    "name": "Thresholding",
    "summary": "Converts the image to pure black and white around a cut-off intensity.",
    "formula": "g(x,y) = 255 if f(x,y) > T else 0",
    "params": [
        {"key": "threshold", "label": "Threshold (T)", "type": "range",
         "min": 0, "max": 255, "step": 1, "default": 127},
    ],
}


def apply(img, params):
    t = get_number(params, "threshold", 127, 0, 255, as_int=True)
    gray = to_gray(img)
    _, binary = cv2.threshold(gray, t, 255, cv2.THRESH_BINARY)
    return binary
