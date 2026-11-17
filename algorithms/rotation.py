"""11. Image Rotation - cv2.getRotationMatrix2D() + cv2.warpAffine() with an expanded canvas."""
import cv2
import numpy as np

from ._utils import get_choice, get_number

INFO = {
    "id": "rotation",
    "name": "Image Rotation",
    "summary": "Rotates around the centre; the canvas grows so no corner is cropped. Positive = counter-clockwise.",
    "formula": "[x'; y'] = [cosθ  sinθ; −sinθ  cosθ] · [x − cx; y − cy] + [cx'; cy']",
    "params": [
        {"key": "angle", "label": "Rotation angle", "type": "range",
         "min": -180, "max": 180, "step": 1, "default": 30, "unit": "°"},
        {"key": "background", "label": "Background", "type": "select", "default": "black",
         "options": [{"value": "black", "label": "Black"}, {"value": "white", "label": "White"}]},
    ],
}


def apply(img, params):
    angle = get_number(params, "angle", 30, -180, 180)
    bg = 255 if get_choice(params, "background", "black", ("black", "white")) == "white" else 0

    h, w = img.shape[:2]
    cx, cy = w / 2.0, h / 2.0
    matrix = cv2.getRotationMatrix2D((cx, cy), angle, 1.0)

    cos, sin = abs(matrix[0, 0]), abs(matrix[0, 1])
    # round(…, 6) first: cos(90°) is 6e-17, and ceil() would otherwise add a spurious extra pixel row/column.
    new_w = int(np.ceil(round(h * sin + w * cos, 6)))
    new_h = int(np.ceil(round(h * cos + w * sin, 6)))
    matrix[0, 2] += new_w / 2.0 - cx   # move the rotated image into the centre of the new canvas
    matrix[1, 2] += new_h / 2.0 - cy

    return cv2.warpAffine(img, matrix, (new_w, new_h), flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=(bg, bg, bg))
