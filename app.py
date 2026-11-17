"""FrameLab - Image Processing Studio. Run with:  python app.py"""
import logging
import os

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

import config
from algorithms._utils import ParamError
from routes import camera_routes, image_routes, page_routes, video_routes
from services.common import ApiError
from services.image_service import cleanup_old_files

log = logging.getLogger("framelab")


def create_app():
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = config.MAX_VIDEO_BYTES + 2 * 1024 * 1024
    app.config["JSON_SORT_KEYS"] = False

    os.makedirs(config.UPLOAD_DIR, exist_ok=True)
    cleanup_old_files()

    app.register_blueprint(page_routes.bp)
    app.register_blueprint(image_routes.bp)
    app.register_blueprint(video_routes.bp)
    app.register_blueprint(camera_routes.bp)

    @app.errorhandler(ApiError)
    def handle_api_error(err):
        return jsonify(error=err.message), err.status

    @app.errorhandler(ParamError)
    def handle_param_error(err):
        return jsonify(error=str(err)), 400

    @app.errorhandler(HTTPException)
    def handle_http_error(err):
        if request.path.startswith("/api/"):
            message = "File is too large." if err.code == 413 else err.description
            return jsonify(error=message), err.code
        return err

    @app.errorhandler(Exception)
    def handle_unexpected(err):
        log.exception("Unhandled error")
        if request.path.startswith("/api/"):
            return jsonify(error="Unexpected server error while processing the request."), 500
        raise err

    @app.after_request
    def no_cache_api(resp):
        if request.path.startswith("/api/") and "Cache-Control" not in resp.headers:
            resp.headers["Cache-Control"] = "no-store"
        return resp

    return app


app = create_app()

if __name__ == "__main__":
    debug = os.environ.get("FRAMELAB_DEBUG") == "1"
    print("FrameLab running at http://127.0.0.1:5000  (Ctrl+C to stop)")
    app.run(host="127.0.0.1", port=5000, debug=debug, threaded=True)
