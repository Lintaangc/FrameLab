"""Image API: methods catalogue, upload, process, histogram, download."""
from flask import Blueprint, jsonify, request, send_file

import config
from algorithms import method_catalog
from services import histogram_service, image_service
from services.common import ApiError, parse_params, require_id

bp = Blueprint("image_api", __name__, url_prefix="/api")


@bp.get("/methods")
def methods():
    return jsonify(methods=method_catalog())


@bp.post("/upload-image")
def upload_image():
    file = request.files.get("image")
    if file is None or not file.filename:
        raise ApiError("No image was uploaded.", 400)
    image_service.validate_image_filename(file.filename)

    data = file.read(config.MAX_IMAGE_BYTES + 1)
    if len(data) > config.MAX_IMAGE_BYTES:
        raise ApiError("Image is too large (limit 16 MB).", 413)
    if not data:
        raise ApiError("The uploaded file is empty.", 400)

    image_service.cleanup_old_files()
    img = image_service.decode_image_bytes(data)
    image_id = image_service.store_original(img)
    return jsonify(
        id=image_id,
        name=file.filename,
        width=int(img.shape[1]),
        height=int(img.shape[0]),
        url=f"/api/image/{image_id}",
        histogram=histogram_service.compute_histogram(img),
    )


@bp.get("/image/<image_id>")
def original_image(image_id):
    path = image_service.original_path(image_id)
    image_service.load_original(image_id)  # 404 JSON if missing
    return send_file(path, mimetype="image/png", max_age=0)


@bp.post("/process-image")
def process_image():
    body = request.get_json(silent=True)
    source = body if isinstance(body, dict) else request.form
    image_id = require_id(source.get("id"))
    params = parse_params(source.get("params"))
    return jsonify(image_service.build_result_payload(image_id, source.get("method"), params))


@bp.get("/histogram")
def histogram():
    image_id = require_id(request.args.get("id"))
    which = request.args.get("which", "original")
    if which == "original":
        img = image_service.load_original(image_id)
    elif which == "result":
        import cv2
        img = cv2.imread(image_service.result_path(image_id), cv2.IMREAD_UNCHANGED)
        if img is None:
            raise ApiError("No processed result yet.", 404)
    else:
        raise ApiError("'which' must be 'original' or 'result'.", 400)
    return jsonify(id=image_id, which=which, histogram=histogram_service.compute_histogram(img))


@bp.get("/download-result")
def download_result():
    import os
    image_id = require_id(request.args.get("id"))
    path = image_service.result_path(image_id)
    if not os.path.isfile(path):
        raise ApiError("No processed result to download yet.", 404)
    return send_file(path, mimetype="image/png", as_attachment=True,
                     download_name="framelab_result.png", max_age=0)


@bp.post("/release")
def release():
    """Delete temporary files of an id (also used with navigator.sendBeacon on page unload)."""
    body = request.get_json(silent=True, force=True)
    if not isinstance(body, dict):
        raise ApiError("Expected a JSON object with an 'id'.", 400)
    image_id = require_id(body.get("id"))
    return jsonify(removed=image_service.release_files(image_id))
