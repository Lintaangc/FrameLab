/* Histogram charts (Chart.js). One instance per card created by the hist_card() macro. */
(function () {
  'use strict';

  const SERIES = {
    r: { label: 'Red', color: '201, 72, 63' },
    g: { label: 'Green', color: '48, 148, 96' },
    b: { label: 'Blue', color: '59, 104, 176' },
    gray: { label: 'Intensity', color: '78, 86, 99' },
  };
  const LABELS = Array.from({ length: 256 }, (_, i) => i);
  const compact = new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 });

  function dataset(key, data) {
    const c = SERIES[key].color;
    return {
      label: SERIES[key].label, data, fill: true, tension: 0, pointRadius: 0, pointHoverRadius: 3,
      borderWidth: 1.3, borderColor: `rgb(${c})`, backgroundColor: `rgba(${c}, .16)`,
    };
  }

  FL.Histogram = class Histogram {
    constructor(prefix) {
      this.canvas = document.getElementById(`${prefix}Canvas`);
      this.wrap = document.getElementById(`${prefix}Wrap`);
      this.legend = document.getElementById(`${prefix}Legend`);
      this.stats = document.getElementById(`${prefix}Stats`);
      this.chart = null;
      this.mode = null;
    }

    _create(datasets) {
      this.chart = new Chart(this.canvas, {
        type: 'line',
        data: { labels: LABELS, datasets },
        options: {
          responsive: true, maintainAspectRatio: false, animation: false,
          interaction: { mode: 'index', intersect: false },
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                title: (items) => `Intensity ${items[0].label}`,
                label: (item) => `${item.dataset.label}: ${item.parsed.y.toLocaleString('en')} px`,
              },
            },
          },
          scales: {
            x: {
              grid: { display: false },
              title: { display: true, text: 'Pixel intensity (0–255)', color: '#667080', font: { size: 11 } },
              ticks: {
                autoSkip: false, maxRotation: 0, color: '#667080', font: { size: 10.5 },
                callback: (value, index) => (index % 64 === 0 || index === 255 ? index : ''),
              },
            },
            y: {
              beginAtZero: true,
              title: { display: true, text: 'Frequency (pixels)', color: '#667080', font: { size: 11 } },
              grid: { color: '#edf0f3' },
              ticks: { maxTicksLimit: 5, color: '#667080', font: { size: 10.5 }, callback: (v) => compact.format(v) },
            },
          },
        },
      });
    }

    /** h = payload from the server: {mode:'rgb'|'gray', r,g,b | gray, stats}. */
    update(h) {
      if (!h) return this.clear();
      if (typeof Chart === 'undefined') {
        this.wrap.querySelector('.hist-empty').textContent = 'Chart.js failed to load';
        return;
      }
      const keys = h.mode === 'rgb' ? ['r', 'g', 'b'] : ['gray'];
      const sets = keys.map((k) => dataset(k, h[k]));
      if (!this.chart) {
        this._create(sets);
      } else if (this.mode !== h.mode) {
        this.chart.data.datasets = sets;
        this.chart.update('none');
      } else {
        sets.forEach((s, i) => { this.chart.data.datasets[i].data = s.data; });
        this.chart.update('none');
      }
      this.mode = h.mode;
      this.wrap.classList.remove('empty');

      this.legend.replaceChildren(...keys.map((k) => {
        const swatch = FL.el('i');
        swatch.style.background = `rgb(${SERIES[k].color})`;
        return FL.el('span', {}, swatch, SERIES[k].label);
      }));
      const s = h.stats;
      this.stats.textContent = `mean ${s.mean} · σ ${s.std} · min ${s.min} · max ${s.max}`;
    }

    clear() {
      this.wrap.classList.add('empty');
      this.legend.replaceChildren();
      this.stats.innerHTML = '&nbsp;';
    }
  };
})();
