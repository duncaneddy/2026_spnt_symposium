// Figures: every renderer draws from deck/data/*.json produced by scripts/*.py.
// Hand-drawn strokes (sketch.js) for frames, axes and diagrams; exact paths for orbits and data.
import { roughLine, roughRect, roughEllipse, roughArrow, roughPolyline, svgEl, strokePath, hashSeed, mulberry32 } from './sketch.js';

export const DATA_FILES = [];

const EASE_IN = 'cubic-bezier(.2,.7,.2,1)';
const EASE_MOVE = 'cubic-bezier(.65,0,.25,1)';
const FILL = { fill: 'both' };
const C = { ink: '#2E2D29', cardinal: '#8C1515', lagunita: '#006CB8', sky: '#0098DB', green: '#279989', gray: '#9A9A9A', board: '#FAF8F3' };
const R_EARTH = 6378.137;

/* ======================= helpers ======================= */

const fmtInt = v => Math.round(v).toLocaleString('en-US');
const fmt = (v, d = 1) => Number(v).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
const sup = n => String(n).replace(/-/g, '−').split('').map(c => '⁰¹²³⁴⁵⁶⁷⁸⁹'['0123456789'.indexOf(c)] ?? (c === '−' ? '⁻' : c)).join('');
const pow10 = e => `10${sup(e)}`;
const sci = (v, digits = 2) => v.toExponential(digits).replace(/e([-+]\d+)/, (m, e) => ` × 10${sup(+e)}`);
const median = a => { const s = [...a].sort((x, y) => x - y); return s.length ? s[Math.floor(s.length / 2)] : NaN; };

function svgFor(el) {
  const w = el.offsetWidth, h = el.offsetHeight;
  return svgEl('svg', { width: w, height: h, viewBox: `0 0 ${w} ${h}` }, el);
}

function text(parent, x, y, str, { size = 24, color = C.ink, anchor = 'start', weight = 400, family = 'var(--sans)', italic = false, cls = '', opacity = 1, baseline = 'alphabetic' } = {}) {
  const t = svgEl('text', { x, y, 'font-size': size, fill: color, 'text-anchor': anchor, 'font-weight': weight, 'font-family': family, 'dominant-baseline': baseline }, parent);
  if (italic) t.setAttribute('font-style', 'italic');
  if (cls) t.setAttribute('class', cls);
  if (opacity !== 1) t.setAttribute('opacity', opacity);
  setText(t, str);
  return t;
}

// SVG text content with each "Pc" typeset as an italic P with subscript c.
function setText(t, str) {
  t.textContent = '';
  String(str).split(/\bPc\b/).forEach((part, i) => {
    if (i) {
      svgEl('tspan', { 'font-family': 'KaTeX_Math, serif', 'font-style': 'italic' }, t).textContent = 'P';
      svgEl('tspan', { dy: '0.3em', 'font-size': '0.7em' }, t).textContent = 'c';
    }
    if (part) { const sp = svgEl('tspan', i ? { dy: '-0.3em' } : {}, t); sp.textContent = part; }
  });
}

// HTML with each "Pc" typeset by KaTeX.

function linPath(pts) { return pts.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(''); }

function exactPath(parent, pts, { color = C.ink, width = 3, opacity = 1, dash = null, fill = 'none', closed = false } = {}) {
  const p = svgEl('path', { d: linPath(pts) + (closed ? 'Z' : ''), stroke: color, 'stroke-width': width, fill, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, parent);
  if (!dash) p.setAttribute('pathLength', 100); else p.setAttribute('stroke-dasharray', dash);
  if (opacity !== 1) p.setAttribute('opacity', opacity);
  return p;
}

const scaleLin = (d0, d1, r0, r1) => v => r0 + (v - d0) / (d1 - d0) * (r1 - r0);
const scaleLog = (d0, d1, r0, r1) => v => r0 + (Math.log10(Math.max(v, 1e-300)) - Math.log10(d0)) / (Math.log10(d1) - Math.log10(d0)) * (r1 - r0);

function niceTicks(a, b, n = 5) {
  const span = b - a, step0 = Math.pow(10, Math.floor(Math.log10(span / n)));
  const step = [1, 2, 2.5, 5, 10].map(m => m * step0).find(s => span / s <= n) || step0 * 10;
  const out = [];
  for (let v = Math.ceil(a / step) * step; v <= b + 1e-9; v += step) out.push(+v.toFixed(10));
  return out;
}

// Axes with hand-drawn lines, exact tick placement. Returns {x, y, g, box}.
function axes(svg, { left = 110, right = 30, top = 20, bottom = 80, xr, yr, xlog = false, ylog = false, xlabel = '', ylabel = '', xticks, yticks, xfmt = v => v, yfmt = v => v, seed = 1 }) {
  const W = +svg.getAttribute('width'), H = +svg.getAttribute('height');
  const x0 = left, x1 = W - right, y0 = H - bottom, y1 = top;
  const x = (xlog ? scaleLog : scaleLin)(xr[0], xr[1], x0, x1);
  const y = (ylog ? scaleLog : scaleLin)(yr[0], yr[1], y0, y1);
  const g = svgEl('g', { class: 'axes' }, svg);
  strokePath(g, roughLine(x0 - 6, y0, x1 + 10, y0, { seed, rough: 0.8 }), { color: 'rgba(46,45,41,.55)', width: 2.2 });
  strokePath(g, roughLine(x0, y0 + 6, x0, y1 - 10, { seed: seed + 1, rough: 0.8 }), { color: 'rgba(46,45,41,.55)', width: 2.2 });
  const xt = xticks || (xlog ? decades(xr) : niceTicks(xr[0], xr[1]));
  const yt = yticks || (ylog ? decades(yr) : niceTicks(yr[0], yr[1]));
  xt.forEach(v => { const px = x(v); svgEl('line', { x1: px, x2: px, y1: y0, y2: y0 + 8, stroke: 'rgba(46,45,41,.45)', 'stroke-width': 2 }, g); text(g, px, y0 + 36, xfmt(v), { size: 22, anchor: 'middle', color: 'rgba(46,45,41,.6)' }); });
  yt.forEach(v => { const py = y(v); svgEl('line', { x1: x0 - 8, x2: x0, y1: py, y2: py, stroke: 'rgba(46,45,41,.45)', 'stroke-width': 2 }, g); text(g, x0 - 14, py + 8, yfmt(v), { size: 22, anchor: 'end', color: 'rgba(46,45,41,.6)' }); });
  if (xlabel) text(g, (x0 + x1) / 2, H - 14, xlabel, { size: 24, anchor: 'middle', color: 'rgba(46,45,41,.7)' });
  if (ylabel) { const t = text(g, 0, 0, ylabel, { size: 24, anchor: 'middle', color: 'rgba(46,45,41,.7)' }); t.setAttribute('transform', `translate(${22} ${(y0 + y1) / 2}) rotate(-90)`); }
  return { x, y, g, box: { x0, x1, y0, y1 } };
}

function decades([a, b]) {
  const out = [];
  for (let e = Math.ceil(Math.log10(Math.min(a, b)) - 1e-9); e <= Math.floor(Math.log10(Math.max(a, b)) + 1e-9); e++) out.push(Math.pow(10, e));
  return out;
}

function drawOnAnim(paths, A, delay = 0, dur = 1300, stagger = 120) {
  paths.forEach((p, i) => {
    if (!p) return;
    if (!p.hasAttribute('pathLength')) { A.push(p.animate([{ opacity: 0 }, { opacity: +(p.getAttribute('opacity') ?? 1) }], { duration: dur, delay: delay + i * stagger, easing: EASE_IN, ...FILL })); return; }
    p.style.strokeDasharray = '100';
    A.push(p.animate([{ strokeDashoffset: 100 }, { strokeDashoffset: 0 }], { duration: dur, delay: delay + i * stagger, easing: 'cubic-bezier(.45,0,.3,1)', ...FILL }));
  });
}
const fadeIn = (el, A, delay = 0, dur = 600) => el && A.push(el.animate([{ opacity: 0 }, { opacity: 1 }], { duration: dur, delay, easing: EASE_IN, ...FILL }));
const popIn = (el, A, delay = 0) => el && A.push(el.animate([{ opacity: 0, transform: 'scale(.6)' }, { opacity: 1, transform: 'scale(1.08)', offset: .7 }, { opacity: 1, transform: 'none' }], { duration: 600, delay, easing: EASE_IN, ...FILL }));

// rAF loop with cancel; fn(tMs) returns false to stop.
function loop(fn) {
  let raf, t0;
  const tick = t => { t0 ??= t; if (fn(t - t0) !== false) raf = requestAnimationFrame(tick); };
  raf = requestAnimationFrame(tick);
  return () => cancelAnimationFrame(raf);
}

function rollNumber(el, from, to, { duration = 1600, delay = 0, log = false, format = fmtInt } = {}) {
  return loop(t => {
    const p = Math.min(1, Math.max(0, (t - delay) / duration)), e = 1 - Math.pow(1 - p, 3);
    const v = log ? Math.pow(10, Math.log10(from) + (Math.log10(to) - Math.log10(from)) * e) : from + (to - from) * e;
    el.textContent = format(v);
    return p < 1;
  });
}

// Orthographic view of ECI points: yaw about z, then tilt toward the viewer.
function projector(cx, cy, kmPerPx, yawDeg = 30, tiltDeg = 22) {
  const yaw = yawDeg * Math.PI / 180, t = tiltDeg * Math.PI / 180, cyw = Math.cos(yaw), syw = Math.sin(yaw), ct = Math.cos(t), st = Math.sin(t);
  return ([x, y, z]) => {
    const x1 = x * cyw - y * syw, y1 = x * syw + y * cyw;
    const y2 = y1 * ct - z * st, z2 = y1 * st + z * ct;
    return [cx + x1 / kmPerPx, cy - z2 / kmPerPx, y2];
  };
}
const hidden = (p, cx, cy, rpx) => p[2] > 0 && Math.hypot(p[0] - cx, p[1] - cy) < rpx;

function earth(svg, cx, cy, r, seed = 11) {
  svgEl('circle', { cx, cy, r, fill: 'rgba(0,108,184,0.05)' }, svg);
  return strokePath(svg, roughEllipse(cx, cy, r, r, { seed, rough: 0.7 }), { color: C.ink, width: 2.6 });
}

function canvasFor(el) {
  const w = el.offsetWidth, h = el.offsetHeight, dpr = 2;
  const cv = document.createElement('canvas');
  cv.width = w * dpr; cv.height = h * dpr; cv.style.width = `${w}px`; cv.style.height = `${h}px`;
  el.appendChild(cv);
  const ctx = cv.getContext('2d'); ctx.scale(dpr, dpr);
  return { cv, ctx, w, h };
}

function legend(svg, x, y, items, { size = 24, gap = 40 } = {}) {
  items.forEach(([label, color, kind = 'line'], i) => {
    const yy = y + i * gap;
    if (kind === 'dot') svgEl('circle', { cx: x + 12, cy: yy - 8, r: 7, fill: color }, svg);
    else if (kind === 'band') svgEl('rect', { x, y: yy - 18, width: 26, height: 18, fill: color, opacity: 0.25 }, svg);
    else svgEl('line', { x1: x, x2: x + 28, y1: yy - 8, y2: yy - 8, stroke: color, 'stroke-width': 4, 'stroke-linecap': 'round' }, svg);
    text(svg, x + 40, yy, label, { size, color: C.ink });
  });
}

// Call fn when the slide reaches `step` by a click; returns a cleanup function.
function onStep(el, step, fn) {
  const sec = el.closest('section');
  const h = e => { if (e.detail.step === step && e.detail.animate) fn(); };
  sec.addEventListener('deckstep', h);
  return () => sec.removeEventListener('deckstep', h);
}

/* ======================= data bindings ======================= */

export const binds = {
};

/* ======================= figures ======================= */

export const figures = {};

/* ---------- orbit path helpers ---------- */
function circOrbit(incDeg, raanDeg, r, n = 240) {
  const i_ = incDeg * Math.PI / 180, O = raanDeg * Math.PI / 180, pts = [];
  for (let k = 0; k <= n; k++) {
    const a = k / n * 2 * Math.PI;
    pts.push([r * (Math.cos(O) * Math.cos(a) - Math.sin(O) * Math.sin(a) * Math.cos(i_)), r * (Math.sin(O) * Math.cos(a) + Math.cos(O) * Math.sin(a) * Math.cos(i_)), r * Math.sin(a) * Math.sin(i_)]);
  }
  return pts;
}

// Split a projected polyline into runs that are in front of / behind the Earth disk.
function frontBack(pp, cx, cy, re) {
  const runs = [];
  let cur = null;
  pp.forEach(p => {
    const h = hidden(p, cx, cy, re);
    if (!cur || cur.h !== h) { if (cur) cur.pts.push([p[0], p[1]]); cur = { h, pts: [] }; runs.push(cur); }
    cur.pts.push([p[0], p[1]]);
  });
  return runs;
}

function circlePts(cx, cy, rx, ry, rot = 0, n = 90) {
  const out = [];
  for (let i = 0; i <= n; i++) { const a = i / n * 2 * Math.PI, x = rx * Math.cos(a), y = ry * Math.sin(a); out.push([cx + x * Math.cos(rot) - y * Math.sin(rot), cy + x * Math.sin(rot) + y * Math.cos(rot)]); }
  return out;
}

// Linear interpolation of a sampled series at time t.
function sampleAt(ts, xs, t) {
  if (t <= ts[0]) return xs[0];
  if (t >= ts[ts.length - 1]) return xs[xs.length - 1];
  let lo = 0, hi = ts.length - 1;
  while (hi - lo > 1) { const m = (lo + hi) >> 1; if (ts[m] <= t) lo = m; else hi = m; }
  const u = (t - ts[lo]) / (ts[hi] - ts[lo]);
  return xs[lo].map((v, k) => v + (xs[hi][k] - v) * u);
}

/* ---------- adopters ---------- */
figures.adopters = {
  render(el) {
    const logos = [['Northwood', 'northwood.svg'], ['Capella', 'capella.svg'], ['D-Orbit USA', 'd-orbit-usa.svg'], ['KSAT', 'ksat.svg'], ['HEO', 'heo.png'], ['Trusted Space', 'trusted-space.png'], ['K2 Space', 'k2-space.svg'], ['Vyoma', 'vyoma.svg'], ['Orbital Sidekick', 'orbital-sidekick.svg']];
    const cols = 4, pitch = 405, cw = 370, W = (cols - 1) * pitch + cw;
    const left = i => { const row = Math.floor(i / cols), inRow = Math.min(cols, logos.length - row * cols); return (W - ((inRow - 1) * pitch + cw)) / 2 + (i % cols) * pitch; };
    el.innerHTML = logos.map(([n, file], i) => `<div class="logo-cell" data-rough="box" data-color="dim" data-rough-key="ad${i}" style="position:absolute; left:${left(i)}px; top:${Math.floor(i / cols) * 190}px; width:370px; height:150px; display:flex; align-items:center; justify-content:center; padding:24px 16px;"><img src="img/logos/${file}" alt="${n}" style="width:100%; height:100%; object-fit:contain;"></div>`).join('');
  },
  animate(el, d, s, A) { [...el.children].forEach((c, i) => A.push(c.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 500, delay: 200 + i * 90, easing: EASE_IN, ...FILL }))); },
};

/* ---------- repo link ---------- */
figures.closeLinks = {
  render(el) {
    const link = (img, alt, label, url) => `<div style="display:flex; align-items:center; gap:32px; height:100%;">${img ? `<img src="${img}" alt="${alt}" style="height:100%;">` : ''}<div class="sans" style="font-size:30px; color:var(--ink-50); line-height:1.4">${label}<br><b style="color:var(--lagunita)">${url}</b></div></div>`;
    el.innerHTML = `<div style="position:absolute; inset:0; display:flex; align-items:center; justify-content:center; gap:90px;">${
      link(null, '', 'Scripts and slides', 'github.com/duncaneddy/<br>2026_spnt_symposium')}${
      link('img/brahe-qr.webp', 'QR code for brahe.space', 'brahe', 'brahe.space')}</div>`;
  },
  animate(el, d, s, A) { fadeIn(el.firstElementChild, A); },
};

/* ======================= slide-level animations ======================= */

export const slideAnims = {};
