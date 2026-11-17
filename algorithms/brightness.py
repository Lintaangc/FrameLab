"""6. Brightness - add a constant to every pixel, clamped to 0–255."""
import numpy as np

from ._utils import get_number

INFO = {
    "id": "brightness",
    "name": "Brightness",
    "summary": "Adds a constant to every pixel. Negative values darken, positive values brighten.",
    "formula": "g(x,y) = clip(f(x,y) + β, 0, 255)",
    "params": [
        {"key": "beta", "label": "Brightness (β)", "type": "range",
         "min": -255, "max": 255, "step": 1, "default": 50},
    ],
}


def apply(img, params):
    beta = get_number(params, "beta", 50, -255, 255, as_int=True)
    # int16 avoids uint8 wrap-around before clipping.
    return np.clip(img.astype(np.int16) + beta, 0, 255).astype(np.uint8)
