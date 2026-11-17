/* Video Processing workspace.
 *
 * JavaScript owns playback; the Python backend owns the pixels. For every frame we handle, the page copies the
 * <video> to a canvas, POSTs it to /api/process-video-frame and draws the returned image next to the original.
 *
 *  - "Near real-time": the original plays at normal speed. One request is in flight at a time; frames that arrive
 *    while the server is busy are skipped (and counted). The result therefore trails the original by a measurable lag.
 *  - "Frame-locked": the page steps the original one frame at a time and waits for each result, so both panes always
 *    show exactly the same instant. Playback is slower than real time; nothing is skipped.
 *  - Whenever playback is paused or the timeline is moved, the exact visible frame is processed, so both panes match.
 */
(async function () {
  'use strict';
  const { $, toast } = FL;
  const MAX_BYTES = 200 * 1024 * 1024;
  const ALLOWED = ['mp4', 'webm', 'mov', 'm4v', 'ogv'];
  const PLAY_ICON = '<svg class="icon" width="18" height="18" viewBox="0 0 24 24"><path d="M8 5.5v13l10-6.5z" fill="currentColor"/></svg>';
  const PAUSE_ICON = '<svg class="icon" width="18" height="18" viewBox="0 0 24 24"><rect x="6.5" y="5.5" width="3.8" height="13" rx="1" fill="currentColor"/><rect x="13.7" y="5.5" width="3.8" height="13" rx="1" fill="currentColor"/></svg>';

  const els = {
    stage: $('#stage'), dropWrap: $('#dropWrap'), dropzone: $('#dropzone'), input: $('#fileInput'), work: $('#workArea'),
    name: $('#fileName'), info: $('#fileInfo'), replace: $('#btnReplace'),
    vid: $('#vid'), canvas: $('#resCanvas'), empty: $('#resEmpty'), origTime: $('#origTime'), resTime: $('#resTime'),
    play: $('#btnPlay'), restart: $('#btnRestart'), timeline: $('#timeline'), tCur: $('#tCur'), tDur: $('#tDur'),
    mode: $('#modeSelect'), width: $('#procWidth'), download: $('#btnDownload'), error: $('#panelError'),
    st: { processed: $('#stProcessed'), skipped: $('#stSkipped'), server: $('#stServer'), round: $('#stRound'), fps: $('#stFps'), lag: $('#stLag') },
  };
  const ctx = els.canvas.getContext('2d');
  const grab = document.createElement('canvas');
  const grabCtx = grab.getContext('2d');
  const histOrig = new FL.Histogram('histOrig');
  const histRes = new FL.Histogram('histRes');

  const S = {
    id: null, info: null,
    playing: false, mode: 'realtime', procWidth: 640,
    runToken: 0,              // changes on every play/pause so stale loops stop
    inflight: false, again: false,
    paramVersion: 0,          // changes when method/params change; older in-flight results are discarded
    processed: 0, skipped: 0, serverMs: null, roundMs: null, stamps: [], lastHistAt: 0,
    hasResult: false, resumeAfterScrub: false, uploading: false, scrubbing: false,
  };

  let methods;
  try {
    methods = await FL.loadMethods();
  } catch (err) {
    els.error.textContent = err.message;
    els.error.hidden = false;
    return;
  }
  const settleSoon = FL.debounce(() => { if (!S.playing && S.id) process(true); }, 180);
  const panel = FL.createMethodPanel($('#methodPanel'), methods, {
    onChange() { S.paramVersion++; settleSoon(); },
  });

  /* ------------------------------------------------------------ helpers */
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const duration = () => (Number.isFinite(els.vid.duration) ? els.vid.duration : (S.info && S.info.duration) || 0);
  const showError = (m) => { els.error.textContent = m || ''; els.error.hidden = !m; };
  const ema = (prev, value) => (prev === null ? value : prev * 0.7 + value * 0.3);

  function updateClock() {
    const t = els.vid.currentTime || 0;
    const d = duration();
    els.tCur.textContent = FL.formatTime(t);
    els.origTime.textContent = FL.formatTime(t);
    if (d > 0 && !S.scrubbing) els.timeline.value = String(Math.round((t / d) * 1000));
  }

  function updatePlayButton() {
    els.play.innerHTML = S.playing ? PAUSE_ICON : PLAY_ICON;
    els.play.setAttribute('aria-label', S.playing ? 'Pause' : 'Play');
  }

  function updateStats(lagMs) {
    els.st.processed.textContent = S.processed;
    els.st.skipped.textContent = S.skipped;
    els.st.server.textContent = S.serverMs === null ? '—' : `${S.serverMs.toFixed(0)} ms`;
    els.st.round.textContent = S.roundMs === null ? '—' : `${S.roundMs.toFixed(0)} ms`;
    if (S.stamps.length >= 2) {
      const span = (S.stamps[S.stamps.length - 1] - S.stamps[0]) / 1000;
      els.st.fps.textContent = span > 0 ? `${((S.stamps.length - 1) / span).toFixed(1)} fps` : '—';
    } else {
      els.st.fps.textContent = '—';
    }
    if (lagMs !== undefined) els.st.lag.textContent = `${Math.round(lagMs)} ms`;
  }

  function resetStats() {
    S.processed = 0; S.skipped = 0; S.serverMs = null; S.roundMs = null; S.stamps = []; S.lastHistAt = 0;
    updateStats();
    els.st.lag.textContent = '—';
  }

  /* ------------------------------------------------------------ frame pipeline */
  function grabFrame(canvas, context, maxWidth, quality) {
    const vw = els.vid.videoWidth, vh = els.vid.videoHeight;
    if (!vw || !vh) return Promise.reject(new Error('The video has no decoded frame yet.'));
    const scale = maxWidth ? Math.min(1, maxWidth / vw) : 1;
    canvas.width = Math.max(1, Math.round(vw * scale));
    canvas.height = Math.max(1, Math.round(vh * scale));
    context.drawImage(els.vid, 0, 0, canvas.width, canvas.height);
    return new Promise((resolve, reject) =>
      canvas.toBlob((b) => (b ? resolve(b) : reject(new Error('Could not capture the frame.'))), 'image/jpeg', quality));
  }

  async function drawResult(dataUrl) {
    const img = new Image();
    img.src = dataUrl;
    await img.decode();
    els.canvas.width = img.naturalWidth;
    els.canvas.height = img.naturalHeight;
    ctx.drawImage(img, 0, 0);
    els.canvas.hidden = false;
    els.empty.hidden = true;
  }

  /**
   * Process the frame that is currently shown by <video>.
   * explicit=true  -> a frame that must be processed (paused, seeked, locked mode): if the server is busy the request is
   *                   remembered and re-run for the then-current frame ("latest wins").
   * explicit=false -> a frame that may be dropped (near real-time playback): counted as skipped when the server is busy.
   * Resolves to 'ok' | 'busy' | 'stale' | 'error'.
   */
  async function process(explicit) {
    if (!S.id) return 'error';
    if (S.inflight) {
      if (explicit) S.again = true;
      else { S.skipped++; updateStats(); }
      return 'busy';
    }
    S.inflight = true;
    const version = S.paramVersion;
    const mediaTime = els.vid.currentTime;
    let status = 'error';
    try {
      const blob = await grabFrame(grab, grabCtx, S.procWidth, 0.85);
      const wantHist = explicit || performance.now() - S.lastHistAt > 300;
      const form = new FormData();
      form.append('frame', blob, 'frame.jpg');
      form.append('method', panel.method);
      form.append('params', JSON.stringify(panel.params()));
      form.append('histograms', wantHist ? '1' : '0');
      const t0 = performance.now();
      const data = await FL.request('/api/process-video-frame', { method: 'POST', body: form });
      const roundTrip = performance.now() - t0;

      if (version !== S.paramVersion) {
        status = 'stale';                           // settings changed while this frame was away
      } else {
        await drawResult(data.frame);
        S.processed++;
        S.serverMs = ema(S.serverMs, data.elapsed_ms);
        S.roundMs = ema(S.roundMs, roundTrip);
        S.stamps.push(performance.now());
        if (S.stamps.length > 12) S.stamps.shift();
        if (data.histogram_original) {
          histOrig.update(data.histogram_original);
          histRes.update(data.histogram_result);
          S.lastHistAt = performance.now();
        }
        els.resTime.textContent = FL.formatTime(mediaTime);
        S.hasResult = true;
        els.download.disabled = false;
        showError('');
        updateStats(Math.max(0, els.vid.currentTime - mediaTime) * 1000);
        status = 'ok';
      }
    } catch (err) {
      showError(err.message);
      status = 'error';
    } finally {
      S.inflight = false;
      if (S.again) { S.again = false; process(true); }
    }
    return status;
  }

  /* ------------------------------------------------------------ playback */
  function seekTo(t) {
    return new Promise((resolve) => {
      let done = false;
      const finish = () => {
        if (done) return;
        done = true;
        els.vid.removeEventListener('seeked', finish);
        requestAnimationFrame(() => resolve());     // let the new frame reach the compositor before we read it
      };
      els.vid.addEventListener('seeked', finish);
      setTimeout(finish, 2500);
      els.vid.currentTime = Math.max(0, Math.min(t, duration()));
    });
  }

  function startRealtime(token) {
    const hasRvfc = typeof els.vid.requestVideoFrameCallback === 'function';
    let lastTime = -1;
    const tick = () => {
      if (token !== S.runToken || !S.playing) return;
      updateClock();
      if (hasRvfc) {
        process(false);                              // one callback per presented video frame
      } else if (els.vid.currentTime !== lastTime) { // fallback: rAF fires faster than the video advances
        lastTime = els.vid.currentTime;
        process(false);
      }
      schedule();
    };
    const schedule = () => (hasRvfc ? els.vid.requestVideoFrameCallback(tick) : requestAnimationFrame(tick));
    schedule();
  }

  async function lockedLoop(token) {
    const fps = S.info && S.info.fps > 0 ? S.info.fps : 30;
    const step = 1 / fps;
    els.vid.pause();
    while (S.playing && token === S.runToken) {
      while (S.inflight) await sleep(15);
      if (token !== S.runToken) return;
      const status = await process(true);
      if (token !== S.runToken) return;
      if (status === 'stale') continue;              // parameters changed mid-flight: redo this same frame
      if (status === 'error') { pause(false); return; }
      const next = els.vid.currentTime + step;
      if (next >= duration() - 0.001) { S.playing = false; updatePlayButton(); updateClock(); return; }
      await seekTo(next);
      updateClock();
    }
  }

  async function play() {
    if (!S.id || S.playing) return;
    if (els.vid.ended || els.vid.currentTime >= duration() - 0.05) await seekTo(0);
    S.playing = true;
    S.runToken++;
    updatePlayButton();
    showError('');
    if (S.mode === 'realtime') {
      try {
        await els.vid.play();
      } catch (err) {
        S.playing = false;
        updatePlayButton();
        showError('The browser could not start playback of this video.');
        return;
      }
      startRealtime(S.runToken);
    } else {
      lockedLoop(S.runToken);
    }
  }

  function pause(settle = true) {
    S.playing = false;
    S.runToken++;
    els.vid.pause();
    updatePlayButton();
    updateClock();
    if (settle && S.id) process(true);               // make the result show exactly the paused frame
  }

  /* ------------------------------------------------------------ loading */
  async function handleFile(file) {
    if (S.uploading) return;
    if (!ALLOWED.includes(FL.fileExt(file.name))) {
      toast('Unsupported video type. Use MP4, WEBM, MOV, M4V or OGV.', 'error');
      return;
    }
    if (file.size > MAX_BYTES) {
      toast('Video is too large (limit 200 MB).', 'error');
      return;
    }
    S.uploading = true;
    const zoneTitle = els.dropzone.querySelector('.dz-title');
    const oldTitle = zoneTitle.textContent;
    els.stage.style.opacity = '.7';
    zoneTitle.textContent = 'Uploading 0%';
    try {
      const form = new FormData();
      form.append('video', file);
      const data = await FL.upload('/api/upload-video', form, (p) => { zoneTitle.textContent = `Uploading ${Math.round(p * 100)}%`; });
      pause(false);
      if (S.id) FL.release(S.id);
      S.id = data.id;
      S.info = data.info;
      S.paramVersion++;
      S.hasResult = false;
      resetStats();
      histOrig.clear(); histRes.clear();
      els.canvas.hidden = true;
      els.empty.hidden = false;
      els.empty.textContent = 'Waiting for the first frame…';
      els.download.disabled = true;
      els.name.textContent = data.name;
      const i = data.info;
      els.info.textContent = `${i.width} × ${i.height} · ${i.fps} fps${i.duration ? ` · ${FL.formatTime(i.duration)}` : ''}`;
      els.tDur.textContent = FL.formatTime(i.duration || 0);
      els.dropWrap.hidden = true;
      els.work.hidden = false;
      els.vid.poster = data.poster;
      els.vid.src = data.url;
      els.vid.load();
      showError('');
    } catch (err) {
      toast(err.message, 'error');
    } finally {
      S.uploading = false;
      zoneTitle.textContent = oldTitle;
      els.stage.style.opacity = '';
    }
  }

  els.vid.addEventListener('loadedmetadata', () => {
    els.tDur.textContent = FL.formatTime(duration());
    updateClock();
  });
  els.vid.addEventListener('loadeddata', () => { if (!S.playing) process(true); });   // first frame -> result pane is never empty
  els.vid.addEventListener('error', () => {
    if (!S.id) return;
    pause(false);
    showError('Your browser cannot play this video (unsupported codec). Try an MP4 (H.264) or WEBM file.');
  });
  els.vid.addEventListener('timeupdate', updateClock);
  els.vid.addEventListener('ended', () => {
    if (S.mode === 'realtime' && S.playing) { S.playing = false; S.runToken++; updatePlayButton(); updateClock(); process(true); }
  });
  els.vid.addEventListener('seeked', () => { if (!S.playing && S.id) process(true); });   // timeline moved while paused

  /* ------------------------------------------------------------ controls */
  els.play.addEventListener('click', () => (S.playing ? pause() : play()));
  els.restart.addEventListener('click', () => {
    pause(false);
    resetStats();
    els.vid.currentTime = 0;           // 'seeked' then processes frame 0
    updateClock();
  });

  els.timeline.addEventListener('pointerdown', () => { S.scrubbing = true; });
  window.addEventListener('pointerup', () => { S.scrubbing = false; });
  els.timeline.addEventListener('input', () => {
    if (!S.id) return;
    if (S.playing) { S.resumeAfterScrub = true; pause(false); }
    els.vid.currentTime = (Number(els.timeline.value) / 1000) * duration();
    els.tCur.textContent = FL.formatTime(els.vid.currentTime);
  });
  els.timeline.addEventListener('change', () => {
    if (S.resumeAfterScrub) { S.resumeAfterScrub = false; play(); }
  });

  els.mode.addEventListener('change', () => {
    const was = S.playing;
    if (was) pause(false);
    S.mode = els.mode.value;
    if (was) play();
  });
  els.width.addEventListener('change', () => {
    S.procWidth = Number(els.width.value);
    S.paramVersion++;
    if (!S.playing) settleSoon();
  });

  els.download.addEventListener('click', async () => {
    if (!S.id || !S.hasResult) return;
    if (S.playing) pause(false);       // freeze the frame that is downloaded
    els.download.disabled = true;
    try {
      const full = document.createElement('canvas');
      const blob = await grabFrame(full, full.getContext('2d'), 0, 0.95);   // native resolution
      const form = new FormData();
      form.append('frame', blob, 'frame.jpg');
      form.append('method', panel.method);
      form.append('params', JSON.stringify(panel.params()));
      form.append('download', '1');
      const response = await fetch('/api/process-video-frame', { method: 'POST', body: form });
      if (!response.ok) {
        const err = await response.json().catch(() => null);
        throw new Error((err && err.error) || `Download failed (${response.status}).`);
      }
      FL.downloadBlob(await response.blob(), `framelab_${panel.method}_${els.vid.currentTime.toFixed(2)}s.png`);
    } catch (err) {
      toast(err.message, 'error');
    } finally {
      els.download.disabled = !S.hasResult;
    }
  });

  FL.setupDropzone({ zone: els.dropzone, input: els.input, dragTarget: els.stage, onFile: handleFile });
  els.replace.addEventListener('click', () => els.input.click());
  window.addEventListener('pagehide', () => FL.release(S.id));
  updatePlayButton();
})();
