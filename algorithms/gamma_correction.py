"""10. Gamma Correction - power-law transform through a look-up table."""
import cv2
import numpy as np

from ._utils import get_number

INFO = {
    "id": "gamma",
    "name": "Gamma Correction",
    "summary": "Non-linear brightness curve. γ > 1 brightens midtones, γ < 1 darkens them.",
    "formula": "g = 255 · (f / 255)^(1/γ)",
    "params": [
        {"key": "gamma", "label": "Gamma (γ)", "type": "range",
         "min": 0.1, "max": 5, "step": 0.05, "default": 1.5},
    ],
}


def build_lut(gamma):
    inv = 1.0 / gamma
    table = (np.arange(256, dtype=np.float64) / 255.0) ** inv * 255.0
    return np.clip(np.rint(table), 0, 255).astype(np.uint8)


def apply(img, params):
    gamma = get_number(params, "gamma", 1.5, 0.1, 5.0)
    return cv2.LUT(img, build_lut(gamma))
