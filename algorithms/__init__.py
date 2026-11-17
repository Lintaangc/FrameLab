"""Registry of the 11 image-processing methods.

Every module exposes `INFO` (metadata + parameter schema used to build the UI)
and `apply(img, params)` which takes a BGR/grayscale uint8 array and returns a NEW array.
"""
import numpy as np

from . import (blur, brightness, contrast_stretching, edge_detection, equalization,
               gamma_correction, grayscale, mirroring, negative, rotation, thresholding)
from ._utils import ParamError

_MODULES = [thresholding, equalization, contrast_stretching, blur, grayscale, brightness,
            negative, mirroring, edge_detection, gamma_correction, rotation]

METHODS = {m.INFO["id"]: m for m in _MODULES}


def method_catalog():
    """Metadata for every method, in presentation order (used by /api/methods and the templates)."""
    return [dict(m.INFO, index=i + 1) for i, m in enumerate(_MODULES)]


def apply_method(method_id, img, params=None):
    module = METHODS.get(method_id)
    if module is None:
        raise ParamError(f"Unknown method '{method_id}'.")
    result = module.apply(img, params or {})
    return np.ascontiguousarray(result)
