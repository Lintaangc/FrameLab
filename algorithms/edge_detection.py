"""9. Edge Detection - Canny (cv2.Canny) and Sobel (cv2.Sobel gradient magnitude)."""
import cv2
import numpy as np

from ._utils import get_choice, get_number, to_gray

INFO = {
    "id": "edges",
    "name": "Edge Detection",
    "summary": "Finds intensity discontinuities. Canny gives thin binary edges; Sobel gives gradient strength.",
    "formula": "Sobel: G = √(Gx² + Gy²)",
    "params": [
        {"key": "algorithm", "label": "Algorithm", "type": "select", "default": "canny",
         "options": [{"value": "canny", "label": "Canny"}, {"value": "sobel", "label": "Sobel"}]},
        {"key": "low", "label": "Low threshold", "type": "range", "min": 0, "max": 255, "step": 1,
         "default": 100, "showIf": {"key": "algorithm", "value": "canny"}},
        {"key": "high", "label": "High threshold", "type": "range", "min": 0, "max": 255, "step": 1,
         "default": 200, "showIf": {"key": "algorithm", "value": "canny"}},
        {"key": "ksize", "label": "Sobel kernel size", "type": "range", "min": 1, "max": 7, "step": 2,
         "default": 3, "showIf": {"key": "algorithm", "value": "sobel"}},
    ],
}


def apply(img, params):
    algorithm = get_choice(params, "algorithm", "canny", ("canny", "sobel"))
    gray = to_gray(img)
    if algorithm == "canny":
        low = get_number(params, "low", 100, 0, 255, as_int=True)
        high = get_number(params, "high", 200, 0, 255, as_int=True)
        if low > high:
            low, high = high, low
        return cv2.Canny(gray, low, high)

    ksize = get_number(params, "ksize", 3, 1, 7, as_int=True)
    if ksize % 2 == 0:
        ksize += 1
    gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=ksize)
    gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=ksize)
    magnitude = np.sqrt(gx ** 2 + gy ** 2)
    peak = magnitude.max()
    if peak > 0:
        magnitude = magnitude / peak * 255.0   # scale gradient strength into 0–255 for display
    return np.clip(np.rint(magnitude), 0, 255).astype(np.uint8)
