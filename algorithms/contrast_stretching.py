"""3. Contrast Stretching - linear mapping [r_min, r_max] -> [0, 255]."""
import numpy as np

from ._utils import ParamError, get_bool, get_number

INFO = {
    "id": "contrast",
    "name": "Contrast Stretching",
    "summary": "Linearly stretches the chosen intensity range to the full 0–255 range. Applied per channel.",
    "formula": "g = (f − r_min) / (r_max − r_min) × 255",
    "params": [
        {"key": "auto", "label": "Use the image's own min / max", "type": "checkbox", "default": False},
        {"key": "r_min", "label": "Minimum intensity (r_min)", "type": "range",
         "min": 0, "max": 254, "step": 1, "default": 30, "showIf": {"key": "auto", "value": False}},
        {"key": "r_max", "label": "Maximum intensity (r_max)", "type": "range",
         "min": 1, "max": 255, "step": 1, "default": 220, "showIf": {"key": "auto", "value": False}},
    ],
}


def apply(img, params):
    if get_bool(params, "auto", False):
        r_min, r_max = float(img.min()), float(img.max())
        if r_max == r_min:          # flat image: nothing to stretch
            return img.copy()
    else:
        r_min = get_number(params, "r_min", 30, 0, 254, as_int=True)
        r_max = get_number(params, "r_max", 220, 1, 255, as_int=True)
        if r_max <= r_min:
            raise ParamError("Maximum intensity must be greater than minimum intensity.")
    f = img.astype(np.float32)
    g = (f - r_min) / (r_max - r_min) * 255.0
    return np.clip(np.rint(g), 0, 255).astype(np.uint8)
