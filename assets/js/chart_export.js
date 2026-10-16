// Renders a clean, shareable PNG of the offense/defense EPA scatter.
// Independent of Chart.js so the export can use its own layout: title block,
// labeled quadrants, collision-avoiding team labels, and a source footer.
(function () {
  const W = 1200;
  const H = 1260;
  const SCALE = 2; // 2400x2520 output
  const FONT = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif';
  const INK = '#0f172a';
  const INK_2 = '#475569';
  const INK_3 = '#94a3b8';
  const GRID = '#e2e8f0';
  const QUADS = {
    tr: { fill: 'rgba(34, 197, 94, 0.07)', text: '#15803d', label: 'Good offense · Good defense' },
    tl: { fill: 'rgba(168, 85, 247, 0.06)', text: '#7e22ce', label: 'Bad offense · Good defense' },
    br: { fill: 'rgba(59, 130, 246, 0.07)', text: '#1d4ed8', label: 'Good offense · Bad defense' },
    bl: { fill: 'rgba(239, 68, 68, 0.07)', text: '#b91c1c', label: 'Bad offense · Bad defense' },
  };
  const DOT_R = 9;

  function niceStep(span, target) {
    const raw = span / target;
    const mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const n = raw / mag;
    return (n < 1.5 ? 1 : n < 3 ? 2 : n < 7 ? 5 : 10) * mag;
  }

  function axisRange(values) {
    let lo = Math.min(0, ...values);
    let hi = Math.max(0, ...values);
    const pad = (hi - lo) * 0.05 || 0.05;
    lo -= pad;
    hi += pad;
    const step = niceStep(hi - lo, 8);
    return { min: Math.floor(lo / step) * step, max: Math.ceil(hi / step) * step, step };
  }

  function fmtTick(v, step) {
    const decimals = Math.max(0, -Math.floor(Math.log10(step)));
    const s = (Math.abs(v) < step / 2 ? 0 : v).toFixed(decimals);
    return v > step / 2 ? `+${s}` : s;
  }

  function overlaps(a, b) {
    return a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
  }

  function circleHitsRect(cx, cy, r, rect) {
    const nx = Math.max(rect.x, Math.min(cx, rect.x + rect.w));
    const ny = Math.max(rect.y, Math.min(cy, rect.y + rect.h));
    return (cx - nx) ** 2 + (cy - ny) ** 2 < r * r;
  }

  // Greedy placement: try positions around each dot (closest first), pick the
  // first that collides with no dot, no placed label, and stays in the plot.
  function placeLabels(ctx, dots, plot) {
    const placed = [];
    const order = dots.slice().sort((a, b) => crowding(b, dots) - crowding(a, dots));
    const g = DOT_R + 3;
    for (const d of order) {
      const w = ctx.measureText(d.label).width + 4;
      const h = 16;
      const cands = [];
      for (const dist of [0, 10, 22, 36]) {
        cands.push(
          { x: d.px + g + dist, y: d.py - h / 2 },
          { x: d.px - g - dist - w, y: d.py - h / 2 },
          { x: d.px - w / 2, y: d.py - g - dist - h },
          { x: d.px - w / 2, y: d.py + g + dist },
          { x: d.px + g * 0.7 + dist, y: d.py - g * 0.7 - dist - h },
          { x: d.px - g * 0.7 - dist - w, y: d.py - g * 0.7 - dist - h },
          { x: d.px + g * 0.7 + dist, y: d.py + g * 0.7 + dist },
          { x: d.px - g * 0.7 - dist - w, y: d.py + g * 0.7 + dist },
        );
      }
      let best = null;
      for (const c of cands) {
        const rect = { x: c.x, y: c.y, w, h };
        if (rect.x < plot.left + 2 || rect.x + w > plot.right - 2 || rect.y < plot.top + 2 || rect.y + h > plot.bottom - 2) continue;
        if (placed.some((p) => overlaps(p.rect, rect))) continue;
        if (dots.some((o) => circleHitsRect(o.px, o.py, DOT_R + 2, rect))) continue;
        best = rect;
        break;
      }
      if (!best) best = { x: d.px + g, y: d.py - h / 2, w, h };
      placed.push({ dot: d, rect: best });
    }
    return placed;
  }

  function crowding(d, dots) {
    return dots.reduce((n, o) => n + (Math.hypot(o.px - d.px, o.py - d.py) < 60 ? 1 : 0), 0);
  }

  function render(opts) {
    const { points, title, subtitle, xLabel, yLabel, footer } = opts;
    const canvas = document.createElement('canvas');
    canvas.width = W * SCALE;
    canvas.height = H * SCALE;
    const ctx = canvas.getContext('2d');
    ctx.scale(SCALE, SCALE);
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, W, H);

    // Title block
    ctx.textBaseline = 'alphabetic';
    ctx.textAlign = 'left';
    ctx.fillStyle = INK;
    ctx.font = `700 34px ${FONT}`;
    ctx.fillText(title, 56, 70);
    ctx.fillStyle = INK_2;
    ctx.font = `400 19px ${FONT}`;
    ctx.fillText(subtitle, 56, 102);

    const plot = { left: 116, right: W - 56, top: 140, bottom: H - 130 };
    const pw = plot.right - plot.left;
    const ph = plot.bottom - plot.top;
    const xr = axisRange(points.map((p) => p.x));
    const yr = axisRange(points.map((p) => p.y));
    const sx = (v) => plot.left + ((v - xr.min) / (xr.max - xr.min)) * pw;
    const sy = (v) => plot.bottom - ((v - yr.min) / (yr.max - yr.min)) * ph;
    const x0 = sx(0);
    const y0 = sy(0);

    // Quadrant tints
    ctx.fillStyle = QUADS.tl.fill; ctx.fillRect(plot.left, plot.top, x0 - plot.left, y0 - plot.top);
    ctx.fillStyle = QUADS.tr.fill; ctx.fillRect(x0, plot.top, plot.right - x0, y0 - plot.top);
    ctx.fillStyle = QUADS.bl.fill; ctx.fillRect(plot.left, y0, x0 - plot.left, plot.bottom - y0);
    ctx.fillStyle = QUADS.br.fill; ctx.fillRect(x0, y0, plot.right - x0, plot.bottom - y0);

    // Grid + ticks
    ctx.lineWidth = 1;
    ctx.font = `400 15px ${FONT}`;
    ctx.fillStyle = INK_2;
    for (let v = xr.min; v <= xr.max + 1e-9; v += xr.step) {
      const x = Math.round(sx(v)) + 0.5;
      ctx.strokeStyle = GRID;
      ctx.beginPath(); ctx.moveTo(x, plot.top); ctx.lineTo(x, plot.bottom); ctx.stroke();
      ctx.textAlign = 'center';
      ctx.fillText(fmtTick(v, xr.step), x, plot.bottom + 24);
    }
    for (let v = yr.min; v <= yr.max + 1e-9; v += yr.step) {
      const y = Math.round(sy(v)) + 0.5;
      ctx.strokeStyle = GRID;
      ctx.beginPath(); ctx.moveTo(plot.left, y); ctx.lineTo(plot.right, y); ctx.stroke();
      ctx.textAlign = 'right';
      ctx.fillText(fmtTick(v, yr.step), plot.left - 12, y + 5);
    }
    // Zero lines
    ctx.strokeStyle = INK_3;
    ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(x0, plot.top); ctx.lineTo(x0, plot.bottom); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(plot.left, y0); ctx.lineTo(plot.right, y0); ctx.stroke();

    // Quadrant labels in the outer corners
    ctx.font = `600 15px ${FONT}`;
    const ql = (q, x, y, align) => { ctx.fillStyle = QUADS[q].text; ctx.textAlign = align; ctx.fillText(QUADS[q].label.toUpperCase(), x, y); };
    ql('tl', plot.left + 14, plot.top + 26, 'left');
    ql('tr', plot.right - 14, plot.top + 26, 'right');
    ql('bl', plot.left + 14, plot.bottom - 14, 'left');
    ql('br', plot.right - 14, plot.bottom - 14, 'right');

    // Axis titles
    ctx.fillStyle = INK;
    ctx.font = `600 17px ${FONT}`;
    ctx.textAlign = 'center';
    ctx.fillText(xLabel, plot.left + pw / 2, plot.bottom + 56);
    ctx.save();
    ctx.translate(40, plot.top + ph / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText(yLabel, 0, 0);
    ctx.restore();

    // Dots
    const dots = points.map((p) => ({ ...p, px: sx(p.x), py: sy(p.y) }));
    for (const d of dots) {
      ctx.beginPath();
      ctx.arc(d.px, d.py, DOT_R, 0, Math.PI * 2);
      ctx.fillStyle = d.color || INK;
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = '#ffffff';
      ctx.stroke();
    }

    // Labels (with leader lines when pushed away from the dot)
    ctx.font = `700 15px ${FONT}`;
    const placed = placeLabels(ctx, dots, plot);
    for (const { dot, rect } of placed) {
      const cx = rect.x + rect.w / 2;
      const cy = rect.y + rect.h / 2;
      const dist = Math.hypot(cx - dot.px, cy - dot.py);
      if (dist > DOT_R + rect.w / 2 + 12) {
        const ex = Math.max(rect.x, Math.min(dot.px, rect.x + rect.w));
        const ey = Math.max(rect.y, Math.min(dot.py, rect.y + rect.h));
        const ang = Math.atan2(ey - dot.py, ex - dot.px);
        ctx.strokeStyle = INK_3;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(dot.px + Math.cos(ang) * (DOT_R + 1), dot.py + Math.sin(ang) * (DOT_R + 1));
        ctx.lineTo(ex, ey);
        ctx.stroke();
      }
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.lineJoin = 'round';
      ctx.lineWidth = 4;
      ctx.strokeStyle = 'rgba(255,255,255,0.9)';
      ctx.strokeText(dot.label, cx, cy + 1);
      ctx.fillStyle = INK;
      ctx.fillText(dot.label, cx, cy + 1);
    }
    ctx.textBaseline = 'alphabetic';

    // Footer
    ctx.strokeStyle = GRID;
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(56, H - 50); ctx.lineTo(W - 56, H - 50); ctx.stroke();
    ctx.font = `400 14px ${FONT}`;
    ctx.fillStyle = INK_3;
    ctx.textAlign = 'left';
    ctx.fillText(footer, 56, H - 24);
    ctx.textAlign = 'right';
    ctx.fillText('ndaly111.github.io/Nflstats', W - 56, H - 24);

    return canvas;
  }

  async function download(opts, filename) {
    const canvas = render(opts);
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/png'));
    if (!blob) return;
    const file = new File([blob], filename, { type: 'image/png' });
    // On phones the share sheet is the way to "Save Image" to Photos.
    const touch = window.matchMedia && window.matchMedia('(pointer: coarse)').matches;
    if (touch && navigator.canShare && navigator.canShare({ files: [file] })) {
      try {
        await navigator.share({ files: [file], title: opts.title });
        return;
      } catch (err) {
        if (err && err.name === 'AbortError') return;
      }
    }
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  window.EpaChartExport = { render, download };
})();
