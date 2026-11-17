"""HTML pages."""
from flask import Blueprint, render_template

from algorithms import method_catalog

bp = Blueprint("pages", __name__)


@bp.get("/")
def index():
    return render_template("index.html", methods=method_catalog())


@bp.get("/image")
def image_processing():
    return render_template("image_processing.html")


@bp.get("/video")
def video_processing():
    return render_template("video_processing.html")


@bp.get("/camera")
def camera():
    return render_template("camera.html")


@bp.get("/about")
def about():
    return render_template("about.html", methods=method_catalog())
