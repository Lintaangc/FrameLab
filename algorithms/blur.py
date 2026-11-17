"""4. Blur - Gaussian, Mean (box) and Median filters."""
import cv2

from ._utils import get_choice, get_number

INFO = {
    "id": "blur",
    "name": "Blur",
    "summary": "Smooths the image. Gaussian weights the neighbourhood, mean averages it, median suits salt-and-pepper noise.",
    "formula": "g = f ∗ h   (h = Gaussian / box kernel, or median of the window)",
    "params": [
        {"key": "filter", "label": "Filter", "type": "select", "default": "gaussian",
         "options": [{"value": "gaussian", "label": "Gaussian"},
                     {"value": "mean", "label": "Mean"},
                     {"value": "median", "label": "Median"}]},
        {"key": "ksize", "label": "Kernel size", "type": "range",
         "min": 1, "max": 31, "step": 2, "default": 5},
    ],
}


def apply(img, params):
    kind = get_choice(params, "filter", "gaussian", ("gaussian", "mean", "median"))
    k = get_number(params, "ksize", 5, 1, 31, as_int=True)
    if k % 2 == 0:          # OpenCV requires an odd kernel for Gaussian and median
        k += 1
    if kind == "gaussian":
        return cv2.GaussianBlur(img, (k, k), 0)
    if kind == "mean":
        return cv2.blur(img, (k, k))
    return cv2.medianBlur(img, k)
