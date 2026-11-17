"""Shared helpers for the algorithm modules."""
import math

import cv2
import numpy as np


class ParamError(ValueError):
    """Raised when a processing parameter is missing, malformed, or out of range."""


def get_number(params, key, default, lo, hi, as_int=False):
    raw = params.get(key, default)
    if isinstance(raw, bool):
        raise ParamError(f"Parameter '{key}' must be a number.")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise ParamError(f"Parameter '{key}' must be a number.")
    if math.isnan(value) or math.isinf(value):
        raise ParamError(f"Parameter '{key}' must be a finite number.")
    if not lo <= value <= hi:
        raise ParamError(f"Parameter '{key}' must be between {lo} and {hi}.")
    return int(round(value)) if as_int else value


def get_choice(params, key, default, choices):
    value = params.get(key, default)
    if value not in choices:
        raise ParamError(f"Parameter '{key}' must be one of: {', '.join(choices)}.")
    return value


def get_bool(params, key, default=False):
    value = params.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


def to_gray(img):
    """BGR -> grayscale using cv2.cvtColor (Y = 0.299 R + 0.587 G + 0.114 B)."""
    if img.ndim == 2:
        return img
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def as_uint8(arr):
    return np.ascontiguousarray(np.clip(arr, 0, 255).astype(np.uint8))
