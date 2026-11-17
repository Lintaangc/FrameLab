"""2. Histogram Equalization - cv2.equalizeHist() on the grayscale image."""
import cv2

from ._utils import to_gray

INFO = {
    "id": "equalization",
    "name": "Histogram Equalization",
    "summary": "Spreads intensities using the cumulative histogram to raise global contrast (grayscale).",
    "formula": "s_k = round(255 · CDF(r_k))",
    "params": [],
}


def apply(img, params):
    return cv2.equalizeHist(to_gray(img))
