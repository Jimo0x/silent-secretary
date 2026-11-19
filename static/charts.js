/* Mini bibliothèque de graphiques Canvas (sans dépendance) — thème noir/rouge */
const Charts = (() => {
  const C = { red: "#e5172f", red2: "#ff3b52", grid: "#26262e", text: "#8d8d99", pal: ["#e5172f", "#ececf1", "#8d8d99", "#ff8a98", "#5d5d69", "#b3122a", "#f5a524", "#5aa9ff", "#2ecc71", "#c084fc"] };
  function setup(cv) {
    const dpr = window.devicePixelRatio || 1, w = cv.clientWidth || cv.width, h = cv.clientHeight || cv.height;
    cv.width = w * dpr; cv.height = h * dpr; const x = cv.getContext("2d"); x.setTransform(dpr, 0, 0, dpr, 0, 0); x.clearRect(0, 0, w, h);
    x.font = "11px Inter, system-ui, sans-serif"; return [x, w, h];
  }
  const nice = v => { if (v <= 0) return 1; const p = Math.pow(10, Math.floor(Math.log10(v))); const n = v / p; return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * p; };
  function axes(x, w, h, max, pad, labels) {
    const top = nice(max), steps = 4;
    x.strokeStyle = C.grid; x.fillStyle = C.text; x.lineWidth = 1;
    for (let i = 0; i <= steps; i++) {
      const y = pad.t + (h - pad.t - pad.b) * (1 - i / steps);
      x.beginPath(); x.moveTo(pad.l, y); x.lineTo(w - pad.r, y); x.stroke();
      const v = top * i / steps; x.textAlign = "right"; x.fillText(v >= 1000 ? (v / 1000).toFixed(1) + "k" : +v.toFixed(2), pad.l - 6, y + 4);
    }
    if (labels) { x.textAlign = "center"; const n = labels.length, every = Math.ceil(n / 10);
      labels.forEach((l, i) => { if (i % every) return; const px = pad.l + (w - pad.l - pad.r) * (n === 1 ? .5 : i / (n - 1)); x.fillText(l, px, h - pad.b + 16); }); }
    return top;
  }
  function line(cv, series, opts = {}) {
    const [x, w, h] = setup(cv); const pad = { l: 44, r: 12, t: 12, b: opts.labels ? 26 : 10 };
    const all = series.flatMap(s => s.data); const max = opts.max ?? Math.max(1e-9, ...all);
    const top = axes(x, w, h, max, pad, opts.labels);
    series.forEach((s, si) => {
      const n = s.data.length; if (!n) return; const col = s.color || C.pal[si % C.pal.length];
      const P = s.data.map((v, i) => [pad.l + (w - pad.l - pad.r) * (n === 1 ? .5 : i / (n - 1)), pad.t + (h - pad.t - pad.b) * (1 - v / top)]);
      if (s.fill !== false && si === 0) { const g = x.createLinearGradient(0, pad.t, 0, h); g.addColorStop(0, col + "55"); g.addColorStop(1, col + "00");
        x.beginPath(); x.moveTo(P[0][0], h - pad.b); P.forEach(p => x.lineTo(...p)); x.lineTo(P[n - 1][0], h - pad.b); x.fillStyle = g; x.fill(); }
      x.beginPath(); P.forEach((p, i) => i ? x.lineTo(...p) : x.moveTo(...p)); x.strokeStyle = col; x.lineWidth = 2; x.setLineDash(s.dash ? [5, 4] : []); x.stroke(); x.setLineDash([]);
      if (s.marks) s.marks.forEach(i => { const p = P[i]; if (!p) return; x.beginPath(); x.arc(p[0], p[1], 4, 0, 7); x.fillStyle = C.red2; x.fill(); });
    });
  }
  function bar(cv, labels, values, opts = {}) {
    const [x, w, h] = setup(cv); const pad = { l: 44, r: 10, t: 12, b: 28 };
    const top = axes(x, w, h, Math.max(1e-9, ...values), pad, null); const n = values.length, bw = (w - pad.l - pad.r) / n;
    values.forEach((v, i) => {
      const bh = (h - pad.t - pad.b) * v / top, bx = pad.l + i * bw + bw * .15, by = h - pad.b - bh;
      const g = x.createLinearGradient(0, by, 0, h - pad.b); g.addColorStop(0, (opts.colors && opts.colors[i]) || C.red2); g.addColorStop(1, (opts.colors && opts.colors[i]) || C.red);
      x.fillStyle = g; x.beginPath(); x.roundRect ? x.roundRect(bx, by, bw * .7, bh, [4, 4, 0, 0]) : x.rect(bx, by, bw * .7, bh); x.fill();
      x.fillStyle = C.text; x.textAlign = "center"; const l = String(labels[i]); x.fillText(l.length > 10 ? l.slice(0, 9) + "…" : l, bx + bw * .35, h - pad.b + 16);
    });
  }
  function donut(cv, labels, values, opts = {}) {
    const [x, w, h] = setup(cv); const tot = values.reduce((a, b) => a + b, 0) || 1; const r = Math.min(w * .5, h) / 2 - 8, cx = r + 8, cy = h / 2;
    let a = -Math.PI / 2;
    values.forEach((v, i) => { const da = v / tot * Math.PI * 2; x.beginPath(); x.arc(cx, cy, r, a, a + da); x.arc(cx, cy, r * .62, a + da, a, true); x.closePath(); x.fillStyle = C.pal[i % C.pal.length]; x.fill(); a += da; });
    x.fillStyle = "#ececf1"; x.textAlign = "center"; x.font = "700 18px Inter, sans-serif"; x.fillText(opts.center ?? tot.toFixed(0), cx, cy + 6);
    x.font = "12px Inter, sans-serif"; x.textAlign = "left";
    labels.forEach((l, i) => { const y = 16 + i * 20; if (y > h - 4) return; x.fillStyle = C.pal[i % C.pal.length]; x.fillRect(cx + r + 20, y - 9, 10, 10); x.fillStyle = "#ececf1";
      x.fillText(`${l}  ${Math.round(values[i] / tot * 100)}%`, cx + r + 36, y); });
  }
  return { line, bar, donut, C };
})();
