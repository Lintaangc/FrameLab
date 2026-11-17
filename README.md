# FrameLab — Image Processing Studio
*Explore, Transform, and Understand Images.*

Proyek akhir Pengolahan Citra Digital. Website pengolahan citra dengan **Flask + OpenCV + NumPy + Pillow** di backend dan **HTML/CSS/JavaScript vanilla + Chart.js** di frontend. Semua hasil dihitung oleh algoritma Python di server; browser hanya menampilkan.

## Menjalankan di Windows
Prasyarat: Python 3.10+ (centang "Add Python to PATH" saat instalasi).

```bat
cd FrameLab
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
Buka **http://127.0.0.1:5000** di Chrome/Edge. (macOS/Linux: `source venv/bin/activate`.)

Catatan:
- Kamera hanya bisa diakses lewat `127.0.0.1` atau `localhost` (aturan keamanan browser). Izinkan akses kamera saat diminta.
- Video yang diputar harus didukung browser: MP4 (H.264), WEBM. Maks 200 MB; gambar maks 16 MB.
- Font DM Sans dimuat dari Google Fonts; tanpa internet otomatis memakai font sistem. Chart.js sudah disertakan lokal (`static/js/vendor`), jadi histogram bekerja offline.
- Tes otomatis: `python -m unittest discover -s tests -v` (33 tes: kebenaran tiap algoritma terhadap rumus, semua route API, validasi error, pembersihan file).

## 11 metode
| # | Metode | Implementasi | Parameter |
|---|---|---|---|
| 1 | Thresholding | `cv2.threshold` (THRESH_BINARY: > T putih, ≤ T hitam) | T 0–255 |
| 2 | Histogram Equalization | `cv2.equalizeHist` pada grayscale | – |
| 3 | Contrast Stretching | g = (f − r_min)/(r_max − r_min)·255, di-clip 0–255 | r_min, r_max (atau otomatis dari min/max citra) |
| 4 | Blur | `cv2.GaussianBlur`, `cv2.blur`, `cv2.medianBlur` | jenis filter, kernel (selalu ganjil) |
| 5 | Grayscale | `cv2.cvtColor` BGR2GRAY, Y = 0.299R + 0.587G + 0.114B | – |
| 6 | Brightness | g = f + β dihitung di int16 lalu di-clip | β −255…255 |
| 7 | Negative | g = 255 − f | – |
| 8 | Mirroring | `cv2.flip` | horizontal / vertikal / keduanya |
| 9 | Edge Detection | `cv2.Canny`; Sobel: G = √(Gx²+Gy²) | low/high (Canny), kernel (Sobel) |
| 10 | Gamma Correction | Look-Up Table `255·(f/255)^(1/γ)` + `cv2.LUT` | γ 0.1–5 |
| 11 | Image Rotation | `getRotationMatrix2D` + `warpAffine`, kanvas diperbesar agar tidak terpotong | sudut −180…180, latar hitam/putih |

Konvensi warna: gambar didekode dengan Pillow (EXIF diterapkan, transparansi diratakan ke putih) lalu dikonversi **RGB→BGR sekali** di batas masuk; seluruh pipeline OpenCV memakai BGR, histogram memetakan kanal 0=Blue, 2=Red. Gambar asli tidak pernah diubah; hasil disimpan terpisah.

## Pemrosesan video (jujur tentang cara kerjanya)
Browser memutar video dan, untuk tiap frame, menyalinnya ke canvas lalu mengirimnya ke `POST /api/process-video-frame`; Python memprosesnya dan hasilnya digambar di sebelah video asli beserta kedua histogram. Dua mode:
- **Near real-time**: video asli diputar normal, satu request berjalan sekali waktu; frame yang datang saat server sibuk dilewati (penghitung *Skipped*) dan *Result lag* menunjukkan selisih waktu hasil terhadap video asli. Ini bukan streaming real-time sejati; kecepatan bergantung komputer dan lebar proses (480/640/960 px).
- **Frame-locked**: video di-seek frame demi frame dan menunggu hasil, sehingga asli dan hasil selalu menampilkan waktu yang persis sama (lebih lambat dari real-time).
Saat pause atau menggeser timeline, frame yang tampil selalu diproses ulang agar keduanya sinkron. *Download Frame* menjeda video dan mengunduh frame hasil beresolusi asli (PNG).

## Struktur & fungsi file
```
app.py                    Factory Flask, registrasi blueprint, penanganan error JSON, start server
config.py                 Batas ukuran, ekstensi, folder upload, TTL file sementara
algorithms/               Satu file per metode: INFO (metadata + skema parameter → membangun UI) dan apply()
  __init__.py             Registry 11 metode: method_catalog(), apply_method()
  _utils.py               Validasi parameter (ParamError), to_gray, helper
routes/                   Hanya validasi request & JSON
  page_routes.py          Halaman HTML
  image_routes.py         /api/methods, upload-image, image/<id>, process-image, histogram, download-result, release
  video_routes.py         upload-video, video/<id> (HTTP Range), video-frame, process-video-frame
  camera_routes.py        capture-process
services/                 Logika
  image_service.py        Dekode/validasi gambar, penyimpanan, pemrosesan, encode, pembersihan file
  video_service.py        cv2.VideoCapture (probe/metadata), proses per frame
  histogram_service.py    Histogram 256-bin dari piksel nyata (RGB atau gray) + statistik
  common.py               ApiError, validasi id (anti path-traversal), parse parameter
templates/                base (sidebar), _components (ikon, kartu histogram), index, image_processing,
                          video_processing, camera, about
static/css/style.css      Desain (putih/abu terang, sidebar charcoal, aksen biru, DM Sans)
static/js/main.js         Helper fetch, toast, dropzone, panel metode/parameter dinamis
static/js/image.js        Workspace gambar (upload, live preview, apply, reset, download)
static/js/video.js        Playback, loop pemrosesan frame, timeline, mode, statistik
static/js/camera.js       MediaDevices API: preview, capture, retake, proses
static/js/histogram.js    Grafik Chart.js (R/G/B atau intensitas)
tests/test_framelab.py    Tes otomatis
uploads/                  File sementara (otomatis dihapus: saat ganti/tinggalkan halaman, dan >1 jam saat upload/start)
```

## Endpoint
`GET /api/methods` · `POST /api/upload-image` · `POST /api/process-image` · `GET /api/histogram?id=&which=original|result` · `GET /api/download-result?id=` · `POST /api/upload-video` · `POST /api/process-video-frame` · `POST /api/capture-process` · `POST /api/release`

## Pemecahan masalah
- *Kamera tidak muncul*: gunakan `http://127.0.0.1:5000`, izinkan kamera, tutup aplikasi lain yang memakai kamera.
- *Video tidak bisa diputar*: konversi ke MP4 H.264 atau WEBM.
- *Video lambat*: pilih lebar proses 480 px atau mode Near real-time.
