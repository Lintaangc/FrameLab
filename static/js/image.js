/* Image Processing workspace: upload -> choose method -> Apply -> compare + histograms. */
(async function () {
  'use strict';
  const { $, toast } = FL;
  const ALLOWED = ['jpg', 'jpeg', 'png', 'bmp', 'webp'];
  const MAX_BYTES = 16 * 1024 * 1024;

  const els = {
    stage: $('#stage'), dropWrap: $('#dropWrap'), dropzone: $('#dropzone'), input: $('#fileInput'), work: $('#workArea'),
    name: $('#fileName'), dims: $('#fileDims'), replace: $('#btnReplace'),
    orig: $('#imgOriginal'), result: $('#imgResult'), empty: $('#resEmpty'), busy: $('#resBusy'),
    origMeta: $('#origMeta'), resMeta: $('#resMeta'), error: $('#panelError'),
    live: $('#liveToggle'), apply: $('#btnApply'), reset: $('#btnReset'), download: $('#btnDownload'),
  };
  const histOrig = new FL.Histogram('histOrig');
  const histRes = new FL.Histogram('histRes');
  const state = { id: null, hasResult: false, seq: 0 };

  let methods;
  try {
    methods = await FL.loadMethods();
  } catch (err) {
    els.error.textContent = err.message;
    els.error.hidden = false;
    return;
  }
  const initial = new URLSearchParams(location.search).get('method');
  const debouncedApply = FL.debounce(() => apply(), 220);
  const panel = FL.createMethodPanel($('#methodPanel'), methods, {
    initial,
    onChange(kind) {
      if (kind === 'reset' || !state.id || !els.live.checked) return;
      debouncedApply();
    },
  });

  function showError(message) {
    els.error.textContent = message || '';
    els.error.hidden = !message;
  }

  function setBusy(on) { els.busy.hidden = !on; }

  function clearResult() {
    state.seq++;                       // invalidates any request still in flight
    debouncedApply.cancel();
    state.hasResult = false;
    els.result.hidden = true;
    els.result.removeAttribute('src');
    els.empty.hidden = false;
    els.resMeta.textContent = '';
    histRes.clear();
    setBusy(false);
    showError('');
    els.download.disabled = true;
  }

  async function handleFile(file) {
    if (!ALLOWED.includes(FL.fileExt(file.name))) {
      toast('Unsupported file type. Use JPG, JPEG, PNG, BMP or WEBP.', 'error');
      return;
    }
    if (file.size > MAX_BYTES) {
      toast('Image is too large (limit 16 MB).', 'error');
      return;
    }
    const form = new FormData();
    form.append('image', file);
    els.stage.style.opacity = '.6';
    try {
      const data = await FL.request('/api/upload-image', { method: 'POST', body: form });
      if (state.id) FL.release(state.id);
      state.id = data.id;
      els.orig.src = data.url;
      els.name.textContent = data.name;
      els.dims.textContent = `${data.width} × ${data.height}`;
      els.origMeta.textContent = `${data.width} × ${data.height}`;
      histOrig.update(data.histogram);
      clearResult();
      els.dropWrap.hidden = true;
      els.work.hidden = false;
      els.apply.disabled = false;
      els.reset.disabled = false;
      toast('Image loaded.', 'ok', 1800);
    } catch (err) {
      toast(err.message, 'error');
    } finally {
      els.stage.style.opacity = '';
    }
  }

  async function apply() {
    if (!state.id) return;
    const seq = ++state.seq;
    setBusy(true);
    showError('');
    try {
      const data = await FL.postJSON('/api/process-image', { id: state.id, method: panel.method, params: panel.params() });
      if (seq !== state.seq) return;       // a newer request or a reset superseded this one
      els.result.src = data.preview;
      els.result.hidden = false;
      els.empty.hidden = true;
      els.resMeta.textContent = `${data.width} × ${data.height} · ${data.elapsed_ms} ms`;
      histRes.update(data.histogram);
      state.hasResult = true;
      els.download.disabled = false;
    } catch (err) {
      if (seq !== state.seq) return;
      showError(err.message);
    } finally {
      if (seq === state.seq) setBusy(false);
    }
  }

  FL.setupDropzone({ zone: els.dropzone, input: els.input, dragTarget: els.stage, onFile: handleFile });
  els.replace.addEventListener('click', () => els.input.click());
  els.apply.addEventListener('click', () => { debouncedApply.cancel(); apply(); });
  els.reset.addEventListener('click', () => {
    clearResult();
    panel.reset();        // restores the default parameters of the selected method
    toast('Reset: result cleared, parameters back to defaults.', 'info', 2200);
  });
  els.download.addEventListener('click', () => {
    if (state.id && state.hasResult) FL.downloadUrl(`/api/download-result?id=${state.id}`, 'framelab_result.png');
  });
  window.addEventListener('pagehide', () => FL.release(state.id));
})();
