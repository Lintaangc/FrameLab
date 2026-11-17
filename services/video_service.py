"""Video storage, OpenCV VideoCapture access and per-frame processing."""
import os
import time
import uuid

import cv2

import config
from algorithms import apply_method
from .common import ApiError, require_id
from .histogram_service import compute_histogram
from .image_service import decode_frame_bytes, extension_of


def _video_path(video_id, ext):
    return os.path.join(config.UPLOAD_DIR, f"{video_id}.{ext}")


def find_video_path(video_id):
    require_id(video_id)
    for ext in config.VIDEO_EXTENSIONS:
        path = _video_path(video_id, ext)
        if os.path.isfile(path):
            return path
    raise ApiError("Video not found or expired. Please upload it again.", 404)


def probe_video(path):
    """Open the file with cv2.VideoCapture, read metadata and make sure a frame can be decoded."""
    cap = cv2.VideoCapture(path)
    try:
        if not cap.isOpened():
            raise ApiError("The video could not be opened.", 400)
        ok, _ = cap.read()
        if not ok:
            raise ApiError("The video contains no readable frames.", 400)
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
        frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    finally:
        cap.release()
    duration = round(frames / fps, 3) if fps > 0 and frames > 0 else None
    return {"fps": round(fps, 2), "frames": frames, "width": width, "height": height, "duration": duration}


def save_video(file_storage):
    ext = extension_of(file_storage.filename)
    if ext not in config.VIDEO_EXTENSIONS:
        allowed = ", ".join(sorted(e.upper() for e in config.VIDEO_EXTENSIONS))
        raise ApiError(f"Unsupported video type. Allowed formats: {allowed}.", 400)
    video_id = uuid.uuid4().hex
    path = _video_path(video_id, ext)
    file_storage.save(path)
    try:
        if os.path.getsize(path) > config.MAX_VIDEO_BYTES:
            raise ApiError("Video is too large (limit 200 MB).", 413)
        info = probe_video(path)
    except Exception:
        if os.path.exists(path):
            os.remove(path)
        raise
    return video_id, info


def read_frame_at(video_id, seconds):
    """Read one frame with cv2.VideoCapture at the given time (used for the poster image)."""
    path = find_video_path(video_id)
    cap = cv2.VideoCapture(path)
    try:
        if seconds > 0:
            cap.set(cv2.CAP_PROP_POS_MSEC, seconds * 1000.0)
        ok, frame = cap.read()
    finally:
        cap.release()
    if not ok:
        raise ApiError("No frame at that time.", 404)
    return frame


def process_frame(frame_bytes, method, params, want_histograms=True):
    """Process one browser-supplied frame with the selected algorithm."""
    if not method:
        raise ApiError("Missing 'method'.", 400)
    frame = decode_frame_bytes(frame_bytes)
    started = time.perf_counter()
    result = apply_method(method, frame, params)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
    payload = {
        "width": int(result.shape[1]),
        "height": int(result.shape[0]),
        "elapsed_ms": elapsed_ms,
    }
    if want_histograms:
        payload["histogram_original"] = compute_histogram(frame)
        payload["histogram_result"] = compute_histogram(result)
    return result, payload
