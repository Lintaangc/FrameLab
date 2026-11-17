"""Image decoding, storage, processing and encoding."""
import base64
import io
import os
import time
import uuid

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

import config
from algorithms import apply_method
from .common import ApiError, require_id
from .histogram_service import compute_histogram


# ---------------------------------------------------------------- validation / decoding
def extension_of(filename):
    if not filename or "." not in filename:
        return ""
    return filename.rsplit(".", 1)[-1].lower()


def validate_image_filename(filename):
    if extension_of(filename) not in config.IMAGE_EXTENSIONS:
        allowed = ", ".join(sorted(e.upper() for e in config.IMAGE_EXTENSIONS))
        raise ApiError(f"Unsupported file type. Allowed formats: {allowed}.", 400)


def limit_size(img):
    h, w = img.shape[:2]
    longest = max(h, w)
    if longest <= config.MAX_IMAGE_SIDE:
        return img
    scale = config.MAX_IMAGE_SIDE / float(longest)
    return cv2.resize(img, (max(1, int(w * scale)), max(1, int(h * scale))), interpolation=cv2.INTER_AREA)


def decode_image_bytes(data):
    """Decode with Pillow (checks the real format, applies EXIF rotation) and return a BGR array."""
    try:
        pil = Image.open(io.BytesIO(data))
        fmt = pil.format
        pil.load()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise ApiError("The file is not a valid image.", 400)
    if fmt not in config.IMAGE_FORMATS:
        raise ApiError("Unsupported image format. Use JPG, PNG, BMP or WEBP.", 400)

    pil = ImageOps.exif_transpose(pil)
    if pil.mode in ("RGBA", "LA", "PA") or (pil.mode == "P" and "transparency" in pil.info):
        rgba = pil.convert("RGBA")                      # flatten transparency onto white
        flat = Image.new("RGB", rgba.size, (255, 255, 255))
        flat.paste(rgba, mask=rgba.getchannel("A"))
        pil = flat
    else:
        pil = pil.convert("RGB")

    rgb = np.asarray(pil)
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)          # explicit RGB -> BGR, once, at the boundary
    return limit_size(bgr)


def decode_frame_bytes(data):
    """Decode a JPEG/PNG frame sent by the browser into BGR."""
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ApiError("Could not decode the frame.", 400)
    return limit_size(img)


# ---------------------------------------------------------------- storage
def _path(file_id, suffix):
    return os.path.join(config.UPLOAD_DIR, f"{file_id}{suffix}")


def original_path(image_id):
    return _path(require_id(image_id), ".png")


def result_path(image_id):
    return _path(require_id(image_id), "_result.png")


def store_original(img):
    image_id = uuid.uuid4().hex
    if not cv2.imwrite(original_path(image_id), img):
        raise ApiError("Could not store the image.", 500)
    return image_id


def load_original(image_id):
    img = cv2.imread(original_path(image_id), cv2.IMREAD_COLOR)
    if img is None:
        raise ApiError("Image not found or expired. Please upload it again.", 404)
    return img


def save_result(image_id, img):
    if not cv2.imwrite(result_path(image_id), img):
        raise ApiError("Could not store the result.", 500)


def cleanup_old_files(max_age=None):
    """Delete temporary files older than the TTL (called at start-up and on every upload)."""
    max_age = config.FILE_TTL_SECONDS if max_age is None else max_age
    cutoff = time.time() - max_age
    try:
        names = os.listdir(config.UPLOAD_DIR)
    except FileNotFoundError:
        return 0
    removed = 0
    for name in names:
        if name.startswith("."):
            continue
        full = os.path.join(config.UPLOAD_DIR, name)
        try:
            if os.path.isfile(full) and os.path.getmtime(full) < cutoff:
                os.remove(full)
                removed += 1
        except OSError:
            pass
    return removed


# ---------------------------------------------------------------- processing / encoding
def encode_preview(img):
    """Data URL for on-screen preview. PNG when small, high-quality JPEG when large."""
    h, w = img.shape[:2]
    if h * w <= config.PREVIEW_PNG_MAX_PIXELS:
        ok, buf = cv2.imencode(".png", img)
        mime = "image/png"
    else:
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 92])
        mime = "image/jpeg"
    if not ok:
        raise ApiError("Could not encode the result.", 500)
    return f"data:{mime};base64," + base64.b64encode(buf.tobytes()).decode("ascii")


def encode_frame(img):
    """Compact JPEG data URL used for video frames."""
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, config.FRAME_JPEG_QUALITY])
    if not ok:
        raise ApiError("Could not encode the frame.", 500)
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode("ascii")


def process_image(image_id, method, params):
    """Run `method` on the stored original. The original file is never modified."""
    if not method:
        raise ApiError("Missing 'method'.", 400)
    original = load_original(image_id)
    started = time.perf_counter()
    result = apply_method(method, original, params)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
    save_result(image_id, result)
    return original, result, elapsed_ms


def build_result_payload(image_id, method, params):
    _, result, elapsed_ms = process_image(image_id, method, params)
    return {
        "id": image_id,
        "method": method,
        "width": int(result.shape[1]),
        "height": int(result.shape[0]),
        "preview": encode_preview(result),
        "histogram": compute_histogram(result),
        "elapsed_ms": elapsed_ms,
    }


def release_files(file_id):
    """Delete every temporary file that belongs to `file_id` (original, result, video).

    Called when the user replaces/retakes a file or leaves the page, so uploads/ does not fill up.
    """
    require_id(file_id)
    removed = 0
    try:
        names = os.listdir(config.UPLOAD_DIR)
    except FileNotFoundError:
        return 0
    for name in names:
        if name.startswith(file_id) and name[len(file_id):len(file_id) + 1] in (".", "_"):
            try:
                os.remove(os.path.join(config.UPLOAD_DIR, name))
                removed += 1
            except OSError:
                pass
    return removed
