"""Histogram computation from real pixel data."""
import cv2
import numpy as np


def _channel_hist(channel):
    hist = cv2.calcHist([np.ascontiguousarray(channel)], [0], None, [256], [0, 256])
    return hist.flatten().astype(np.int64).tolist()


def compute_histogram(img):
    """Return {'mode': 'gray'|'rgb', ...256-bin lists..., 'stats': {...}}.

    OpenCV stores colour as BGR, so channel 0 is Blue and channel 2 is Red.
    """
    if img.ndim == 2 or img.shape[2] == 1:
        gray = img if img.ndim == 2 else img[:, :, 0]
        data = {"mode": "gray", "gray": _channel_hist(gray)}
    else:
        data = {
            "mode": "rgb",
            "b": _channel_hist(img[:, :, 0]),
            "g": _channel_hist(img[:, :, 1]),
            "r": _channel_hist(img[:, :, 2]),
        }
    data["stats"] = {
        "mean": round(float(img.mean()), 2),
        "std": round(float(img.std()), 2),
        "min": int(img.min()),
        "max": int(img.max()),
    }
    return data
