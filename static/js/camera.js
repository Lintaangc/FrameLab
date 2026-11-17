/* Camera Capture: MediaDevices live preview -> capture -> process with any method. */
(async function () {
  'use strict';
  const { $, toast } = FL;

  const els = {
    video: $('#camVideo'), captured: $('#imgCaptured'), empty: $('#camEmpty'), start: $('#btnStart'),
    capture: $('#btnCapture'), retake: $('#btnRetake'), stop: $('#btnStop'), process: $('#btnProcess'), download: $('#btnDownload'),
    result: $('#imgResult'), resEmpty: $('#resEmpty'), busy: $('#resBusy'), resMeta: $('#resMeta'), camMeta: $('#camMeta'),
    paneTitle: $('#paneTitle'), camError: $('#camError'), panelError: $('#panelError'),
  };
  const histOrig = new FL.Histogram('histOrig');
  const histRes = new FL.Histogram('histRes');
  const state = { stream: null, blob: null, id: null, seq: 0, hasResult: false };

  let methods;
  try {
    methods = await FL.loadMethods();
  } catch (err) {
    els.panelError.textContent = err.message;
    els.panelError.hidden = false;
    return;
  }
  const panel = FL.createMethodPanel($('#methodPanel'), methods, {});

  const setError = (el, msg) => { el.textContent = msg || ''; el.hidden = !msg; };

  function cameraMessage(err) {
    switch (err && err.name) {
      case 'NotAllowedError': case 'SecurityError': return 'Camera permission was denied. Allow camera access in the browser address bar and try again.';
      case 'NotFoundError': case 'OverconstrainedError': return 'No camera was found on this computer.';
      case 'NotReadableError': case 'AbortError': return 'The camera is in use by another application. Close it and try again.';
      default: return `Could not start the camera${err && err.message ? `: ${err.message}` : '.'}`;
    }
  }

  function syncButtons() {
    const live = !!state.stream;
    const captured = !!state.blob;
    els.capture.disabled = !live || captured;
    els.retake.disabled = !captured;
    els.process.disabled = !captured;
    els.stop.hidden = !live;
    els.download.disabled = !state.hasResult;
  }

  function clearResult() {
    state.seq++;
    state.hasResult = false;
    els.result.hidden = true;
    els.result.removeAttribute('src');
    els.resEmpty.hidden = false;
    els.busy.hidden = true;
    els.resMeta.textContent = '';
    histRes.clear();
    setError(els.panelError, '');
  }

  async function startCamera() {
    setError(els.camError, '');
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setError(els.camError, 'This browser cannot access the camera here. Open FrameLab at http://127.0.0.1:5000 or http://localhost:5000 (camera access requires a secure context).');
      return;
    }
    els.start.disabled = true;
    try {
      state.stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'user' }, audio: false,
      });
      els.video.srcObject = state.stream;
      await els.video.play().catch(() => {});
      els.empty.hidden = true;
      els.video.hidden = false;
      els.paneTitle.textContent = 'Live camera';
      const track = state.stream.getVideoTracks()[0];
      track.addEventListener('ended', () => { if (state.stream) stopCamera(); });
      const s = track.getSettings();
      els.camMeta.textContent = s.width ? `${s.width} × ${s.height}` : '';
    } catch (err) {
      setError(els.camError, cameraMessage(err));
    } finally {
      els.start.disabled = false;
      syncButtons();
    }
  }

  function stopCamera() {
    if (state.stream) state.stream.getTracks().forEach((t) => t.stop());
    state.stream = null;
    els.video.srcObject = null;
    els.video.hidden = true;
    if (!state.blob) {
      els.empty.hidden = false;
      els.paneTitle.textContent = 'Camera';
      els.camMeta.textContent = '';
    }
    syncButtons();
  }

  function capture() {
    const v = els.video;
    if (!v.videoWidth) { toast('The camera is not ready yet.', 'error'); return; }
    const canvas = document.createElement('canvas');
    canvas.width = v.videoWidth;
    canvas.height = v.videoHeight;
    canvas.getContext('2d').drawImage(v, 0, 0);
    canvas.toBlob((blob) => {
      if (!blob) { toast('Could not capture the photo.', 'error'); return; }
      state.blob = blob;
      if (state.id) FL.release(state.id);
      state.id = null;
      clearResult();
      URL.revokeObjectURL(els.captured.src);
      els.captured.src = URL.createObjectURL(blob);
      els.captured.hidden = false;
      els.video.hidden = true;
      els.paneTitle.textContent = 'Captured photo';
      els.camMeta.textContent = `${canvas.width} × ${canvas.height}`;
      histOrig.clear();
      syncButtons();
    }, 'image/png');
  }

  function retake() {
    state.blob = null;
    if (state.id) FL.release(state.id);
    state.id = null;
    clearResult();
    histOrig.clear();
    els.captured.hidden = true;
    els.captured.removeAttribute('src');
    if (state.stream) {
      els.video.hidden = false;
      els.paneTitle.textContent = 'Live camera';
    } else {
      els.empty.hidden = false;
      els.paneTitle.textContent = 'Camera';
      els.camMeta.textContent = '';
    }
    syncButtons();
  }

  async function processImage() {
    if (!state.blob) return;
    const seq = ++state.seq;
    els.busy.hidden = false;
    setError(els.panelError, '');
    els.process.disabled = true;
    try {
      const form = new FormData();
      form.append('method', panel.method);
      form.append('params', JSON.stringify(panel.params()));
      if (state.id) form.append('id', state.id);          // re-process the capture that is already on the server
      else form.append('image', state.blob, 'capture.png'); // first time: upload the photo
      const data = await FL.request('/api/capture-process', { method: 'POST', body: form });
      if (seq !== state.seq) { if (data.new_capture) FL.release(data.id); return; }
      state.id = data.id;
      if (data.histogram_original) histOrig.update(data.histogram_original);
      els.result.src = data.preview;
      els.result.hidden = false;
      els.resEmpty.hidden = true;
      els.resMeta.textContent = `${data.width} × ${data.height} · ${data.elapsed_ms} ms`;
      histRes.update(data.histogram);
      state.hasResult = true;
    } catch (err) {
      if (seq === state.seq) {
        setError(els.panelError, err.message);
        if (/not found|expired/i.test(err.message)) state.id = null;   // server dropped it: upload again next time
      }
    } finally {
      if (seq === state.seq) els.busy.hidden = true;
      els.process.disabled = !state.blob;
      syncButtons();
    }
  }

  els.start.addEventListener('click', startCamera);
  els.stop.addEventListener('click', stopCamera);
  els.capture.addEventListener('click', capture);
  els.retake.addEventListener('click', retake);
  els.process.addEventListener('click', processImage);
  els.download.addEventListener('click', () => {
    if (state.id && state.hasResult) FL.downloadUrl(`/api/download-result?id=${state.id}`, 'framelab_result.png');
  });
  window.addEventListener('pagehide', () => {
    if (state.stream) state.stream.getTracks().forEach((t) => t.stop());
    FL.release(state.id);
  });
  syncButtons();
})();
