/* FrameLab shared helpers: DOM, fetch wrapper, toasts, dropzone, and the method/parameter panel. */
(function () {
  'use strict';
  const FL = (window.FL = {});

  FL.$ = (selector, root = document) => root.querySelector(selector);

  FL.el = function (tag, attrs = {}, ...children) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs)) {
      if (value === null || value === undefined || value === false) continue;
      if (key === 'class') node.className = value;
      else if (key === 'text') node.textContent = value;
      else node.setAttribute(key, value === true ? '' : value);
    }
    for (const child of children) node.append(child);
    return node;
  };

  /* ---------------------------------------------------------------- toasts */
  FL.toast = function (message, kind = 'info', ms = 4500) {
    const host = FL.$('#toasts');
    if (!host) return;
    const node = FL.el('div', { class: `toast ${kind}`, role: kind === 'error' ? 'alert' : 'status', text: message });
    host.append(node);
    setTimeout(() => node.remove(), ms);
  };

  /* ---------------------------------------------------------------- network */
  FL.request = async function (url, options = {}) {
    let response;
    try {
      response = await fetch(url, options);
    } catch (err) {
      throw new Error('Cannot reach the FrameLab server. Is it still running?');
    }
    let data = null;
    if ((response.headers.get('content-type') || '').includes('application/json')) {
      data = await response.json().catch(() => null);
    }
    if (!response.ok) throw new Error((data && data.error) || `Request failed (${response.status}).`);
    return data;
  };

  FL.postJSON = (url, body) =>
    FL.request(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

  /** Multipart upload with progress (fetch cannot report upload progress). */
  FL.upload = function (url, formData, onProgress) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', url);
      xhr.responseType = 'json';
      if (onProgress) {
        xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total);
      }
      xhr.onerror = () => reject(new Error('Cannot reach the FrameLab server. Is it still running?'));
      xhr.onload = () => {
        const data = xhr.response;
        if (xhr.status >= 200 && xhr.status < 300) resolve(data);
        else reject(new Error((data && data.error) || `Upload failed (${xhr.status}).`));
      };
      xhr.send(formData);
    });
  };

  /** Ask the server to delete the temporary files of an id (best effort, survives page unload). */
  FL.release = function (id) {
    if (!id) return;
    const payload = JSON.stringify({ id });
    try {
      if (navigator.sendBeacon && navigator.sendBeacon('/api/release', new Blob([payload], { type: 'application/json' }))) return;
    } catch (_) { /* fall through */ }
    fetch('/api/release', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: payload, keepalive: true }).catch(() => {});
  };

  let methodsPromise = null;
  FL.loadMethods = () => (methodsPromise ||= FL.request('/api/methods').then((d) => d.methods));

  /* ---------------------------------------------------------------- misc */
  FL.debounce = function (fn, wait) {
    let timer = null;
    const wrapped = (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), wait); };
    wrapped.cancel = () => clearTimeout(timer);
    return wrapped;
  };

  FL.formatTime = function (seconds) {
    if (!Number.isFinite(seconds) || seconds < 0) seconds = 0;
    const m = Math.floor(seconds / 60);
    const s = seconds - m * 60;
    return `${String(m).padStart(2, '0')}:${s.toFixed(1).padStart(4, '0')}`;
  };

  FL.downloadBlob = function (blob, filename) {
    const url = URL.createObjectURL(blob);
    FL.downloadUrl(url, filename);
    setTimeout(() => URL.revokeObjectURL(url), 4000);
  };

  FL.downloadUrl = function (url, filename) {
    const a = FL.el('a', { href: url, download: filename || '' });
    document.body.append(a);
    a.click();
    a.remove();
  };

  FL.fileExt = (name) => (name.includes('.') ? name.split('.').pop().toLowerCase() : '');

  /* ---------------------------------------------------------------- dropzone */
  FL.setupDropzone = function ({ zone, input, dragTarget, onFile }) {
    const target = dragTarget || zone;
    input.addEventListener('click', (e) => e.stopPropagation());
    zone.addEventListener('click', () => input.click());
    zone.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); input.click(); }
    });
    input.addEventListener('change', () => {
      const file = input.files && input.files[0];
      input.value = '';
      if (file) onFile(file);
    });

    const hasFiles = (e) => e.dataTransfer && Array.from(e.dataTransfer.types || []).includes('Files');
    let depth = 0;
    target.addEventListener('dragenter', (e) => { if (!hasFiles(e)) return; e.preventDefault(); depth++; target.classList.add('dragging'); });
    target.addEventListener('dragover', (e) => { if (hasFiles(e)) e.preventDefault(); });
    target.addEventListener('dragleave', () => { depth = Math.max(0, depth - 1); if (!depth) target.classList.remove('dragging'); });
    target.addEventListener('drop', (e) => {
      if (!hasFiles(e)) return;
      e.preventDefault();
      depth = 0;
      target.classList.remove('dragging');
      const file = e.dataTransfer.files && e.dataTransfer.files[0];
      if (file) onFile(file);
    });
  };
  // A file dropped outside a dropzone must not make the browser navigate away from the page.
  window.addEventListener('dragover', (e) => e.preventDefault());
  window.addEventListener('drop', (e) => e.preventDefault());

  /* ---------------------------------------------------------------- method panel */
  /**
   * Builds the method selector and its parameter controls from the server's catalogue.
   * onChange(kind) is called with 'method' | 'param' | 'reset'.
   */
  FL.createMethodPanel = function (container, methods, options = {}) {
    const onChange = options.onChange || (() => {});
    let current = methods.find((m) => m.id === options.initial) || methods[0];
    let values = {};

    const select = FL.el('select', { class: 'select', id: 'methodSelect' });
    for (const m of methods) {
      select.append(FL.el('option', { value: m.id, text: `${String(m.index).padStart(2, '0')} · ${m.name}` }));
    }
    select.value = current.id;

    const info = FL.el('div', { class: 'method-info' });
    const paramsHost = FL.el('div', { class: 'params' });
    container.replaceChildren(
      FL.el('label', { class: 'field-label', for: 'methodSelect', text: 'Processing method' }),
      FL.el('div', { class: 'select-wrap' }, select),
      info, paramsHost,
    );

    const decimals = (step) => { const s = String(step); return s.includes('.') ? s.split('.')[1].length : 0; };
    const format = (p, v) => `${Number(v).toFixed(decimals(p.step || 1))}${p.unit || ''}`;

    function applyVisibility() {
      for (const node of paramsHost.querySelectorAll('[data-show-key]')) {
        const expected = node.dataset.showValue;
        node.hidden = String(values[node.dataset.showKey]) !== expected;
      }
    }

    function build() {
      info.replaceChildren(FL.el('span', { text: current.summary }), FL.el('code', { text: current.formula }));
      paramsHost.replaceChildren();
      values = {};
      if (!current.params.length) {
        paramsHost.append(FL.el('p', { class: 'hint', text: 'This method has no parameters.' }));
        return;
      }
      for (const p of current.params) {
        values[p.key] = p.default;
        const id = `param-${p.key}`;
        const field = FL.el('div', { class: 'field' });
        if (p.showIf) { field.dataset.showKey = p.showIf.key; field.dataset.showValue = String(p.showIf.value); }

        if (p.type === 'range') {
          const out = FL.el('output', { class: 'range-val', for: id, text: format(p, p.default) });
          const input = FL.el('input', { type: 'range', id, min: p.min, max: p.max, step: p.step, value: p.default });
          input.addEventListener('input', () => {
            values[p.key] = Number(input.value);
            out.textContent = format(p, input.value);
            onChange('param');
          });
          field.append(FL.el('label', { for: id }, FL.el('span', { text: p.label }), out), input);
        } else if (p.type === 'select') {
          const input = FL.el('select', { class: 'select', id });
          for (const o of p.options) input.append(FL.el('option', { value: o.value, text: o.label }));
          input.value = p.default;
          input.addEventListener('change', () => { values[p.key] = input.value; applyVisibility(); onChange('param'); });
          field.append(FL.el('label', { for: id, text: p.label }), FL.el('div', { class: 'select-wrap' }, input));
        } else if (p.type === 'checkbox') {
          const input = FL.el('input', { type: 'checkbox', id });
          input.checked = !!p.default;
          input.addEventListener('change', () => { values[p.key] = input.checked; applyVisibility(); onChange('param'); });
          field.append(FL.el('label', { class: 'check', for: id }, input, FL.el('span', { text: p.label })));
        }
        paramsHost.append(field);
      }
      applyVisibility();
    }

    select.addEventListener('change', () => {
      current = methods.find((m) => m.id === select.value);
      build();
      onChange('method');
    });
    build();

    return {
      get method() { return current.id; },
      get info() { return current; },
      params: () => ({ ...values }),
      reset() { build(); onChange('reset'); },
      setMethod(id) { if (methods.some((m) => m.id === id)) { select.value = id; select.dispatchEvent(new Event('change')); } },
    };
  };
})();
