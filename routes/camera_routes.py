"""Webcam capture API."""
from flask import Blueprint, jsonify, request

import config
from services import histogram_service, image_service
from services.common import ApiError, parse_params, require_id

bp = Blueprint("camera_api", __name__, url_prefix="/api")


@bp.post("/capture-process")
def capture_process():
    """Process a captured photo.

    First call: send the photo as multipart field `image` -> it is stored and gets an id.
    Later calls: send only `id` (+ new method/params) to re-process the same capture.
    """
    method = request.form.get("method")
    params = parse_params(request.form.get("params"))
    file = request.files.get("image")

    new_capture = file is not None
    extra = {}
    if new_capture:
        data = file.read(config.MAX_IMAGE_BYTES + 1)
        if not data:
            raise ApiError("The captured image is empty.", 400)
        if len(data) > config.MAX_IMAGE_BYTES:
            raise ApiError("Captured image is too large.", 413)
        image_service.cleanup_old_files()
        img = image_service.decode_image_bytes(data)
        image_id = image_service.store_original(img)
        extra["histogram_original"] = histogram_service.compute_histogram(img)
        extra["url"] = f"/api/image/{image_id}"
    else:
        image_id = require_id(request.form.get("id"))

    payload = image_service.build_result_payload(image_id, method, params)
    payload.update(extra, new_capture=new_capture)
    return jsonify(payload)
