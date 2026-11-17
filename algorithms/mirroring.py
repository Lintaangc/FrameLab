"""8. Mirroring - cv2.flip()."""
import cv2

from ._utils import get_choice

INFO = {
    "id": "mirroring",
    "name": "Mirroring",
    "summary": "Flips the image across its vertical axis, horizontal axis, or both.",
    "formula": "g(x,y) = f(W−1−x, y)   |   f(x, H−1−y)",
    "params": [
        {"key": "direction", "label": "Direction", "type": "select", "default": "horizontal",
         "options": [{"value": "horizontal", "label": "Horizontal flip"},
                     {"value": "vertical", "label": "Vertical flip"},
                     {"value": "both", "label": "Both"}]},
    ],
}

_FLIP_CODES = {"horizontal": 1, "vertical": 0, "both": -1}


def apply(img, params):
    direction = get_choice(params, "direction", "horizontal", tuple(_FLIP_CODES))
    return cv2.flip(img, _FLIP_CODES[direction])
