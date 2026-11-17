"""Automated checks for FrameLab. Run from the project folder:  python -m unittest discover -s tests -v"""
import io
import json
import os
import sys
import tempfile
import unittest

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402

_TMP = tempfile.TemporaryDirectory()
config.UPLOAD_DIR = _TMP.name          # tests never touch the real uploads/ folder

from algorithms import METHODS, apply_method, method_catalog  # noqa: E402
from algorithms._utils import ParamError  # noqa: E402
from algorithms.gamma_correction import build_lut  # noqa: E402
from app import create_app  # noqa: E402


def sample_bgr(h=60, w=80, seed=1):
    rng = np.random.default_rng(seed)
    img = rng.integers(0, 256, (h, w, 3), dtype=np.uint8)
    img[:, : w // 2, 0] = 200           # make the channels distinguishable (B high on the left half)
    return img


def png_bytes(img):
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def jpg_bytes(img):
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    return buf.tobytes()


class AlgorithmTests(unittest.TestCase):
    def setUp(self):
        self.img = sample_bgr()
        self.gray = cv2.cvtColor(self.img, cv2.COLOR_BGR2GRAY)

    def test_eleven_methods_registered(self):
        self.assertEqual(len(METHODS), 11)
        self.assertEqual(len(method_catalog()), 11)

    def test_input_never_mutated(self):
        for m in METHODS:
            before = self.img.copy()
            apply_method(m, self.img, {})
            self.assertTrue(np.array_equal(before, self.img), m)

    def test_all_defaults_return_uint8(self):
        for m in METHODS:
            out = apply_method(m, self.img, {})
            self.assertEqual(out.dtype, np.uint8, m)

    def test_thresholding(self):
        out = apply_method("thresholding", self.img, {"threshold": 100})
        self.assertTrue(np.array_equal(out, np.where(self.gray > 100, 255, 0).astype(np.uint8)))
        self.assertEqual(set(np.unique(out)), {0, 255})
        # boundary: pixel == T becomes black
        flat = np.full((4, 4, 3), 100, np.uint8)
        self.assertEqual(int(apply_method("thresholding", flat, {"threshold": 100}).max()), 0)

    def test_equalization(self):
        out = apply_method("equalization", self.img, {})
        self.assertTrue(np.array_equal(out, cv2.equalizeHist(self.gray)))

    def test_contrast_stretching_manual(self):
        out = apply_method("contrast", self.img, {"auto": False, "r_min": 50, "r_max": 200})
        ref = np.clip(np.rint((self.img.astype(np.float32) - 50) / 150 * 255), 0, 255).astype(np.uint8)
        self.assertTrue(np.array_equal(out, ref))
        self.assertEqual(out.min(), 0)
        self.assertEqual(out.max(), 255)

    def test_contrast_stretching_auto_and_invalid(self):
        narrow = np.clip(self.img // 4 + 60, 0, 255).astype(np.uint8)
        out = apply_method("contrast", narrow, {"auto": True})
        self.assertEqual((int(out.min()), int(out.max())), (0, 255))
        with self.assertRaises(ParamError):
            apply_method("contrast", self.img, {"r_min": 200, "r_max": 100})

    def test_blur_variants_and_kernel_rules(self):
        for kind, fn in (("gaussian", lambda i, k: cv2.GaussianBlur(i, (k, k), 0)),
                         ("mean", lambda i, k: cv2.blur(i, (k, k))),
                         ("median", lambda i, k: cv2.medianBlur(i, k))):
            out = apply_method("blur", self.img, {"filter": kind, "ksize": 7})
            self.assertTrue(np.array_equal(out, fn(self.img, 7)), kind)
        # an even kernel is rounded up to the next odd number instead of crashing OpenCV
        even = apply_method("blur", self.img, {"filter": "median", "ksize": 6})
        self.assertTrue(np.array_equal(even, cv2.medianBlur(self.img, 7)))
        a = apply_method("blur", self.img, {"filter": "gaussian", "ksize": 3})
        b = apply_method("blur", self.img, {"filter": "gaussian", "ksize": 15})
        self.assertFalse(np.array_equal(a, b))

    def test_grayscale_luminance(self):
        out = apply_method("grayscale", self.img, {})
        self.assertEqual(out.ndim, 2)
        b, g, r = (self.img[..., i].astype(np.float64) for i in range(3))
        ref = 0.299 * r + 0.587 * g + 0.114 * b
        self.assertLessEqual(np.abs(out.astype(np.float64) - ref).max(), 1.0)
        # BGR order is respected: a pure red pixel must be darker than a pure green one
        px = np.array([[[0, 0, 255], [0, 255, 0]]], np.uint8)
        gr = apply_method("grayscale", px, {})
        self.assertLess(int(gr[0, 0]), int(gr[0, 1]))

    def test_brightness_clamps(self):
        up = apply_method("brightness", self.img, {"beta": 80})
        self.assertTrue(np.array_equal(up, np.clip(self.img.astype(int) + 80, 0, 255).astype(np.uint8)))
        down = apply_method("brightness", self.img, {"beta": -80})
        self.assertTrue(np.array_equal(down, np.clip(self.img.astype(int) - 80, 0, 255).astype(np.uint8)))
        self.assertEqual(int(apply_method("brightness", np.full((2, 2, 3), 250, np.uint8), {"beta": 100}).min()), 255)
        self.assertEqual(int(apply_method("brightness", np.full((2, 2, 3), 5, np.uint8), {"beta": -100}).max()), 0)

    def test_negative(self):
        out = apply_method("negative", self.img, {})
        self.assertTrue(np.array_equal(out, 255 - self.img))
        self.assertTrue(np.array_equal(apply_method("negative", out, {}), self.img))

    def test_mirroring(self):
        self.assertTrue(np.array_equal(apply_method("mirroring", self.img, {"direction": "horizontal"}), self.img[:, ::-1]))
        self.assertTrue(np.array_equal(apply_method("mirroring", self.img, {"direction": "vertical"}), self.img[::-1]))
        self.assertTrue(np.array_equal(apply_method("mirroring", self.img, {"direction": "both"}), self.img[::-1, ::-1]))

    def test_edges(self):
        canny = apply_method("edges", self.img, {"algorithm": "canny", "low": 60, "high": 150})
        self.assertTrue(np.array_equal(canny, cv2.Canny(self.gray, 60, 150)))
        loose = apply_method("edges", self.img, {"algorithm": "canny", "low": 5, "high": 20})
        self.assertGreater(int((loose > 0).sum()), int((canny > 0).sum()))
        sobel = apply_method("edges", self.img, {"algorithm": "sobel", "ksize": 3})
        gx = cv2.Sobel(self.gray, cv2.CV_64F, 1, 0, ksize=3)
        gy = cv2.Sobel(self.gray, cv2.CV_64F, 0, 1, ksize=3)
        mag = np.sqrt(gx ** 2 + gy ** 2)
        ref = np.clip(np.rint(mag / mag.max() * 255), 0, 255).astype(np.uint8)
        self.assertTrue(np.array_equal(sobel, ref))
        # a vertical step edge must light up only at the step
        step = np.zeros((20, 20), np.uint8)
        step[:, 10:] = 255
        out = apply_method("edges", step, {"algorithm": "sobel"})
        self.assertGreater(int(out[:, 9:11].min()), 0)
        self.assertEqual(int(out[:, :7].max()), 0)

    def test_gamma_lut(self):
        lut = build_lut(2.0)
        expected = np.rint(255 * (np.arange(256) / 255.0) ** 0.5).astype(np.uint8)
        self.assertTrue(np.array_equal(lut, expected))
        self.assertEqual((int(lut[0]), int(lut[255])), (0, 255))
        bright = apply_method("gamma", self.img, {"gamma": 2.0}).mean()
        dark = apply_method("gamma", self.img, {"gamma": 0.5}).mean()
        self.assertGreater(bright, self.img.mean())
        self.assertLess(dark, self.img.mean())

    def test_rotation_expands_canvas(self):
        img = np.full((40, 100, 3), 200, np.uint8)
        r90 = apply_method("rotation", img, {"angle": 90})
        self.assertEqual(r90.shape[:2], (100, 40))
        r0 = apply_method("rotation", img, {"angle": 0})
        self.assertTrue(np.array_equal(r0, img))
        r45 = apply_method("rotation", img, {"angle": 45})
        self.assertGreater(r45.shape[0], 40)
        self.assertGreater(r45.shape[1], 100 * np.cos(np.pi / 4) - 1)
        # nothing cropped: the amount of non-background area is preserved (within interpolation error)
        self.assertAlmostEqual(float((r45[..., 0] > 100).sum()), 40 * 100, delta=40 * 100 * 0.08)
        white = apply_method("rotation", img, {"angle": 45, "background": "white"})
        self.assertEqual(int(white[0, 0, 0]), 255)

    def test_grayscale_input_accepted_everywhere(self):
        for m in METHODS:
            apply_method(m, self.gray, {})

    def test_parameter_validation(self):
        bad = [("thresholding", {"threshold": 999}), ("thresholding", {"threshold": "abc"}),
               ("brightness", {"beta": 1000}), ("gamma", {"gamma": 0}), ("blur", {"filter": "x"}),
               ("blur", {"ksize": 400}), ("rotation", {"angle": float("nan")}), ("mirroring", {"direction": "x"})]
        for method, params in bad:
            with self.assertRaises(ParamError, msg=(method, params)):
                apply_method(method, self.img, params)
        with self.assertRaises(ParamError):
            apply_method("nope", self.img, {})


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = create_app()
        app.testing = True
        cls.client = app.test_client()
        cls.img = sample_bgr(90, 120)

    def upload(self, data=None, name="test.png"):
        data = data if data is not None else png_bytes(self.img)
        return self.client.post("/api/upload-image", data={"image": (io.BytesIO(data), name)},
                                content_type="multipart/form-data")

    def process(self, image_id, method, params=None):
        return self.client.post("/api/process-image", json={"id": image_id, "method": method, "params": params or {}})

    def test_pages_render(self):
        for path in ("/", "/image", "/video", "/camera", "/about", "/image?method=blur"):
            r = self.client.get(path)
            self.assertEqual(r.status_code, 200, path)
        self.assertIn(b"FrameLab", self.client.get("/").data)

    def test_methods_endpoint(self):
        data = self.client.get("/api/methods").get_json()
        self.assertEqual(len(data["methods"]), 11)
        self.assertEqual([m["index"] for m in data["methods"]], list(range(1, 12)))

    def test_upload_formats(self):
        for ext, enc in (("png", png_bytes), ("jpg", jpg_bytes), ("jpeg", jpg_bytes)):
            r = self.upload(enc(self.img), f"x.{ext}")
            self.assertEqual(r.status_code, 200, ext)
        for ext, params in (("bmp", ".bmp"), ("webp", ".webp")):
            ok, buf = cv2.imencode(params, self.img)
            self.assertTrue(ok)
            self.assertEqual(self.upload(buf.tobytes(), f"x.{ext}").status_code, 200, ext)

    def test_upload_errors(self):
        self.assertEqual(self.upload(b"not an image", "x.png").status_code, 400)
        self.assertEqual(self.upload(png_bytes(self.img), "x.gif").status_code, 400)
        self.assertEqual(self.upload(b"", "x.png").status_code, 400)
        self.assertEqual(self.client.post("/api/upload-image").status_code, 400)
        # a text file with an image extension is rejected by content, not by name
        self.assertEqual(self.upload(b"hello world" * 100, "fake.jpg").status_code, 400)

    def test_every_method_via_api_matches_algorithm(self):
        image_id = self.upload().get_json()["id"]
        original = cv2.imdecode(np.frombuffer(png_bytes(self.img), np.uint8), cv2.IMREAD_COLOR)
        for method in METHODS:
            r = self.process(image_id, method)
            self.assertEqual(r.status_code, 200, method)
            payload = r.get_json()
            self.assertIn("histogram", payload)
            dl = self.client.get(f"/api/download-result?id={image_id}")
            self.assertEqual(dl.status_code, 200)
            self.assertEqual(dl.mimetype, "image/png")
            got = cv2.imdecode(np.frombuffer(dl.data, np.uint8), cv2.IMREAD_UNCHANGED)
            dl.close()
            expected = apply_method(method, original, {})
            self.assertTrue(np.array_equal(got, expected), f"{method}: downloaded result differs from the algorithm output")

    def test_original_unchanged_and_params_matter(self):
        image_id = self.upload().get_json()["id"]
        h_before = self.client.get(f"/api/histogram?id={image_id}&which=original").get_json()["histogram"]
        a = self.process(image_id, "brightness", {"beta": 60}).get_json()["histogram"]
        b = self.process(image_id, "brightness", {"beta": -60}).get_json()["histogram"]
        self.assertNotEqual(a["r"], b["r"])
        h_after = self.client.get(f"/api/histogram?id={image_id}&which=original").get_json()["histogram"]
        self.assertEqual(h_before, h_after)
        res = self.client.get(f"/api/histogram?id={image_id}&which=result").get_json()["histogram"]
        self.assertEqual(res["r"], b["r"])

    def test_histogram_is_real_pixel_data(self):
        image_id = self.upload().get_json()["id"]
        h = self.client.get(f"/api/histogram?id={image_id}&which=original").get_json()["histogram"]
        self.assertEqual(h["mode"], "rgb")
        for ch in "rgb":
            self.assertEqual(len(h[ch]), 256)
            self.assertEqual(sum(h[ch]), 90 * 120)
        self.assertEqual(np.array(h["b"]).argmax(), 200)       # B channel is 200 on the left half of the sample
        g = self.process(image_id, "grayscale").get_json()["histogram"]
        self.assertEqual(g["mode"], "gray")
        self.assertEqual(sum(g["gray"]), 90 * 120)
        t = self.process(image_id, "thresholding", {"threshold": 127}).get_json()["histogram"]["gray"]
        self.assertEqual(sum(t[1:255]), 0)                      # binary image: only bins 0 and 255 are used

    def test_process_errors(self):
        image_id = self.upload().get_json()["id"]
        self.assertEqual(self.process(image_id, "thresholding", {"threshold": 500}).status_code, 400)
        self.assertEqual(self.process(image_id, "bogus").status_code, 400)
        self.assertEqual(self.process(image_id, None).status_code, 400)
        self.assertEqual(self.process("0" * 32, "negative").status_code, 404)
        self.assertEqual(self.process("../etc/passwd", "negative").status_code, 400)
        self.assertEqual(self.client.get("/api/download-result?id=" + "0" * 32).status_code, 404)
        self.assertEqual(self.client.get("/api/image/..%2f..%2fconfig").status_code, 404)

    def test_capture_process_flow(self):
        r = self.client.post("/api/capture-process", data={
            "image": (io.BytesIO(png_bytes(self.img)), "capture.png"), "method": "negative", "params": "{}"},
            content_type="multipart/form-data")
        self.assertEqual(r.status_code, 200)
        first = r.get_json()
        self.assertTrue(first["new_capture"])
        self.assertIn("histogram_original", first)
        r2 = self.client.post("/api/capture-process", data={"id": first["id"], "method": "gamma", "params": json.dumps({"gamma": 2})},
                              content_type="multipart/form-data")
        self.assertEqual(r2.status_code, 200)
        self.assertFalse(r2.get_json()["new_capture"])
        self.assertEqual(self.client.post("/api/capture-process", data={"method": "negative"}).status_code, 400)

    def test_video_frame_processing(self):
        frame = jpg_bytes(self.img)
        r = self.client.post("/api/process-video-frame", data={
            "frame": (io.BytesIO(frame), "f.jpg"), "method": "edges", "params": json.dumps({"algorithm": "sobel"})},
            content_type="multipart/form-data")
        self.assertEqual(r.status_code, 200)
        p = r.get_json()
        self.assertTrue(p["frame"].startswith("data:image/jpeg;base64,"))
        self.assertIn("histogram_original", p)
        self.assertIn("histogram_result", p)
        no_hist = self.client.post("/api/process-video-frame", data={
            "frame": (io.BytesIO(frame), "f.jpg"), "method": "negative", "histograms": "0"},
            content_type="multipart/form-data").get_json()
        self.assertNotIn("histogram_original", no_hist)
        dl = self.client.post("/api/process-video-frame", data={
            "frame": (io.BytesIO(frame), "f.jpg"), "method": "negative", "download": "1"},
            content_type="multipart/form-data")
        self.assertEqual(dl.mimetype, "image/png")
        self.assertEqual(self.client.post("/api/process-video-frame", data={"method": "negative"}).status_code, 400)
        bad = self.client.post("/api/process-video-frame", data={"frame": (io.BytesIO(b"junk"), "f.jpg"), "method": "negative"},
                               content_type="multipart/form-data")
        self.assertEqual(bad.status_code, 400)

    def _make_video(self, ext="mp4v", name="clip.mp4", frames=24, fps=12):
        path = os.path.join(_TMP.name, "src_" + name)
        w, h = 160, 96
        writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*ext), fps, (w, h))
        if not writer.isOpened():
            self.skipTest("this OpenCV build cannot write test videos")
        for i in range(frames):
            f = np.zeros((h, w, 3), np.uint8)
            f[:, :] = (i * 10 % 256, 90, 160)
            cv2.rectangle(f, (i * 5, 20), (i * 5 + 30, 60), (255, 255, 255), -1)
            writer.write(f)
        writer.release()
        return path

    def test_video_upload_stream_and_frames(self):
        path = self._make_video()
        with open(path, "rb") as fh:
            r = self.client.post("/api/upload-video", data={"video": (fh, "clip.mp4")}, content_type="multipart/form-data")
        self.assertEqual(r.status_code, 200, r.data)
        data = r.get_json()
        self.assertEqual(data["info"]["frames"], 24)
        self.assertAlmostEqual(data["info"]["fps"], 12, delta=0.5)
        self.assertEqual((data["info"]["width"], data["info"]["height"]), (160, 96))
        s = self.client.get(data["url"], headers={"Range": "bytes=0-99"})
        self.assertEqual(s.status_code, 206)
        f0 = self.client.get(f"/api/video-frame?id={data['id']}&t=0")
        f1 = self.client.get(f"/api/video-frame?id={data['id']}&t=1.5")
        self.assertEqual(f0.status_code, 200)
        self.assertNotEqual(f0.data, f1.data)                  # different times -> different frames
        self.assertEqual(self.client.post("/api/release", json={"id": data["id"]}).get_json()["removed"], 1)
        self.assertEqual(self.client.get(data["url"]).status_code, 404)

    def test_video_upload_errors(self):
        r = self.client.post("/api/upload-video", data={"video": (io.BytesIO(b"x" * 500), "a.mp4")}, content_type="multipart/form-data")
        self.assertEqual(r.status_code, 400)
        r = self.client.post("/api/upload-video", data={"video": (io.BytesIO(b"x"), "a.exe")}, content_type="multipart/form-data")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.client.post("/api/upload-video").status_code, 400)
        self.assertEqual([n for n in os.listdir(_TMP.name) if n.endswith(".mp4") and not n.startswith("src_")], [])  # failed uploads are removed

    def test_release_and_cleanup(self):
        import time
        from services import image_service
        image_id = self.upload().get_json()["id"]
        self.process(image_id, "negative")
        self.assertEqual(self.client.post("/api/release", json={"id": image_id}).get_json()["removed"], 2)
        self.assertEqual(self.client.post("/api/release", json={"id": "nope"}).status_code, 400)
        old = os.path.join(_TMP.name, "old.png")
        open(old, "wb").write(b"x")
        past = time.time() - config.FILE_TTL_SECONDS - 60
        os.utime(old, (past, past))
        self.assertGreaterEqual(image_service.cleanup_old_files(), 1)
        self.assertFalse(os.path.exists(old))

    def test_large_image_is_downscaled(self):
        big = np.zeros((100, config.MAX_IMAGE_SIDE + 500, 3), np.uint8)
        r = self.upload(png_bytes(big), "big.png").get_json()
        self.assertEqual(r["width"], config.MAX_IMAGE_SIDE)

    def test_png_with_alpha_flattened_on_white(self):
        rgba = np.zeros((10, 10, 4), np.uint8)       # fully transparent
        r = self.upload(png_bytes(rgba), "a.png")
        self.assertEqual(r.status_code, 200)
        out = self.process(r.get_json()["id"], "grayscale").get_json()["histogram"]["gray"]
        self.assertEqual(out[255], 100)

    def test_rgb_not_bgr_after_decode(self):
        # a pure red PNG must stay red: B and G histograms at 0, R histogram at 255
        red = np.zeros((8, 8, 3), np.uint8)
        red[..., 2] = 255
        h = self.upload(png_bytes(red), "red.png").get_json()["histogram"]
        self.assertEqual(h["r"][255], 64)
        self.assertEqual(h["b"][0], 64)


if __name__ == "__main__":
    unittest.main()
