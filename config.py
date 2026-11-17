"""Application-wide settings for FrameLab."""
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

if os.environ.get("VERCEL"):
    UPLOAD_DIR = "/tmp/uploads"
else:
    UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")

IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "bmp", "webp"}
IMAGE_FORMATS = {"JPEG", "PNG", "BMP", "WEBP"}   # verified by Pillow, not only by extension
VIDEO_EXTENSIONS = {"mp4", "webm", "mov", "m4v", "ogv"}  # formats browsers can play

MAX_IMAGE_BYTES = 16 * 1024 * 1024
MAX_VIDEO_BYTES = 200 * 1024 * 1024
MAX_FRAME_BYTES = 12 * 1024 * 1024
MAX_IMAGE_SIDE = 4096            # larger images are downscaled on upload (protects memory)

FILE_TTL_SECONDS = 60 * 60       # temporary files older than this are deleted
FRAME_JPEG_QUALITY = 85          # transport quality of processed video frames
PREVIEW_PNG_MAX_PIXELS = 1_500_000  # bigger previews are sent as JPEG; downloads are always PNG