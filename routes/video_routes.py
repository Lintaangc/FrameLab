"""Video API."""
import io
import mimetypes

import cv2
from flask import Blueprint, Response, jsonify, request, send_file

import config
from services import image_service, video_service
from services.common import ApiError, parse_params, require_id

bp = Blueprint("video_api", __name__, url_prefix="/api")


@bp.post("/upload-video")
def upload_video():
    file = request.files.get("video")
    if file is None or not file.filename:
        raise ApiError("No video was uploaded.", 400)
    image_service.cleanup_old_files()
    video_id, info = video_service.save_video(file)
    return jsonify(
        id=video_id,
        name=file.filename,
        url=f"/api/video/{video_id}",
        poster=f"/api/video-frame?id={video_id}&t=0",
        info=info,
    )


@bp.get("/video/<video_id>")
def stream_video(video_id):
    path = video_service.find_video_path(video_id)
    mime = mimetypes.guess_type(path)[0] or "video/mp4"
    return send_file(path, mimetype=mime, conditional=True, max_age=0)  # conditional => HTTP Range (seeking)


@bp.get("/video-frame")
def video_frame():
    """A single frame read with cv2.VideoCapture (used for the poster image)."""
    video_id = require_id(request.args.get("id"))
    try:
        seconds = max(0.0, float(request.args.get("t", "0")))
    except ValueError:
        raise ApiError("'t' must be a number of seconds.", 400)
    frame = video_service.read_frame_at(video_id, seconds)
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        raise ApiError("Could not encode the frame.", 500)
    return Response(buf.tobytes(), mimetype="image/jpeg", headers={"Cache-Control": "no-store"})


@bp.post("/process-video-frame")
def process_video_frame():
    """Process one frame captured by the browser from the playing video.

    multipart fields: frame (JPEG/PNG), method, params (JSON string),
                      histograms ('1'/'0', default '1'), download ('1' -> return a PNG file)
    """
    file = request.files.get("frame")
    if file is None:
        raise ApiError("No frame was sent.", 400)
    data = file.read(config.MAX_FRAME_BYTES + 1)
    if not data:
        raise ApiError("The frame is empty.", 400)
    if len(data) > config.MAX_FRAME_BYTES:
        raise ApiError("Frame is too large.", 413)

    method = request.form.get("method")
    params = parse_params(request.form.get("params"))
    download = request.form.get("download") == "1"
    want_hist = request.form.get("histograms", "1") == "1" and not download

    result, payload = video_service.process_frame(data, method, params, want_histograms=want_hist)

    if download:
        ok, buf = cv2.imencode(".png", result)
        if not ok:
            raise ApiError("Could not encode the frame.", 500)
        return send_file(io.BytesIO(buf.tobytes()), mimetype="image/png", as_attachment=True,
                         download_name="framelab_video_frame.png", max_age=0)

    payload["frame"] = image_service.encode_frame(result)
    return jsonify(payload)
