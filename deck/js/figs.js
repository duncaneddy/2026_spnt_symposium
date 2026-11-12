// Figures: every renderer draws from deck/data/*.json produced by scripts/*.py.
// Hand-drawn strokes (sketch.js) for frames, axes and diagrams; exact paths for orbits and data.
import { roughLine, roughRect, roughEllipse, roughArrow, roughPolyline, svgEl, strokePath, hashSeed, mulberry32 } from './sketch.js';

export const DATA_FILES = ['skyplot', 'quick_hits', 'land', 'gps_constellation'];

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

// Project facts shown on the brahe introduction slide.
const BRAHE = { since: 2014, license: 'MIT', core: 'Rust', bindings: 'Python' };

const PT_TIME = new Intl.DateTimeFormat('en-US', { timeZone: 'America/Los_Angeles', hour: 'numeric', minute: '2-digit' });
const PT_DATE = new Intl.DateTimeFormat('en-US', { timeZone: 'America/Los_Angeles', month: 'long', day: 'numeric', year: 'numeric' });
const last = a => a[a.length - 1];
const prn = n => `G${String(n).padStart(2, '0')}`;

export const binds = {
  'brahe.since': () => String(BRAHE.since),
  'brahe.license': () => BRAHE.license,
  'brahe.core': () => BRAHE.core,
  'brahe.bindings': () => BRAHE.bindings,
  'gps.n': d => String(d.gps_constellation.prns.length),
  'gps.date': d => PT_DATE.format(new Date(d.gps_constellation.talk_epoch_utc ?? d.gps_constellation.epoch_utc)),
  'gps.product': d => d.gps_constellation.product.replace(/\.SP3(\.gz)?$/i, ''),
  'sky.nVisible': d => String(d.skyplot.n_visible),
  'sky.mask': d => fmt(d.skyplot.el_mask_deg, 0),
  'sky.timePT': d => PT_TIME.format(new Date(d.skyplot.epoch_utc)).replace(/\s?([AP])M$/, (m, a) => ` ${a.toLowerCase()}.m.`),
  'sky.datePT': d => PT_DATE.format(new Date(d.skyplot.epoch_utc)),
  'sky.timeUTC': d => `${d.skyplot.epoch_utc.slice(0, 10)} ${d.skyplot.epoch_utc.slice(11, 16)} UTC`,
  'sky.product': d => d.skyplot.product.replace(/\.SP3(\.gz)?$/i, ''),
  'qh.nGps': d => String(d.quick_hits.tle.n),
  'qh.nTracks': d => String(d.quick_hits.tle.tracks.length),
  'qh.object': d => d.quick_hits.propagate.object,
  'qh.days': d => fmt(last(d.quick_hits.propagate.t_h) / 24, 0),
  'qh.drEnd': d => fmtInt(last(d.quick_hits.propagate.dr_km)),
  'qh.drDragEnd': d => fmt(last(d.quick_hits.propagate.dr_drag_km), 1),
  'qh.prn': d => prn(d.quick_hits.frames.prn),
  'qh.frameH': d => fmt(last(d.quick_hits.frames.t_h), 0),
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

/* ---------- code cards ---------- */
// Python source lines with brahe calls in Lagunita, keywords semibold, comments gray.
const PY_KW = /^(?:import|from|as|for|in|if|else|elif|def|return|with|lambda|not|and|or|None|True|False|class|try|except|while)$/;
const escHTML = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

function pyHTML(line) {
  const re = /(#.*$)|("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')|\b(bh(?:\.[A-Za-z_]\w*)+)|\b([A-Za-z_]\w*)\b/g;
  let out = '', i = 0, m;
  while ((m = re.exec(line))) {
    out += escHTML(line.slice(i, m.index));
    i = re.lastIndex;
    if (m[1]) out += `<span class="cm">${escHTML(m[1])}</span>`;
    else if (m[2]) out += `<span class="st">${escHTML(m[2])}</span>`;
    else if (m[3]) out += `<span class="bh">${m[3]}</span>`;
    else out += PY_KW.test(m[4]) ? `<span class="kw">${m[4]}</span>` : m[4];
  }
  return out + escHTML(line.slice(i));
}

// Monospace code inside a hand-drawn box that spans the width of el; its height follows the lines.
//   lines      source lines, one string per line ('' for a blank line)
//   highlight  1-based line numbers drawn in Cardinal; [n, step] turns line n Cardinal on click `step`
//   steps      {lineNumber: step}: the line stays hidden until that click
//   size       font size in px (22 minimum)
//   key        seed for the hand-drawn box, so clones redraw the same outline
function codeCard(el, lines, { highlight = [], steps = {}, size = 22, key = '' } = {}) {
  const box = document.createElement('div');
  box.className = 'code-card';
  box.dataset.rough = 'box';
  box.dataset.roughKey = `code-${key || lines[0]}`;
  box.style.fontSize = `${Math.max(22, size)}px`;
  const pre = document.createElement('pre');
  const hl = new Map(highlight.map(h => (Array.isArray(h) ? h : [h, 0])));
  lines.forEach((ln, i) => {
    const n = i + 1, row = document.createElement('div');
    row.className = 'ln';
    row.innerHTML = pyHTML(ln) || '​';
    if (hl.get(n) === 0) row.classList.add('hl');
    else if (hl.has(n)) {
      const over = document.createElement('span');
      over.className = 'ln-hl';
      over.textContent = ln;
      over.dataset.step = hl.get(n);
      row.appendChild(over);
    }
    if (steps[n]) row.dataset.step = steps[n];
    pre.appendChild(row);
  });
  box.appendChild(pre);
  el.appendChild(box);
  return box;
}

// Code shown on slides: real lines from the named script, trimmed to the lines that matter.
// Each entry becomes the figure `code-<key>` (use <div class="fig" data-fig="code-<key>">), which
// shows the data-pending note while the script's JSON is missing.
const CODE = {
  skyplot: {
    needs: ['skyplot'],
    lines: [
      'sp3 = bh.SP3.from_file(str(path))',
      'site_ecef = bh.position_geodetic_to_ecef(',
      '    STANFORD_LLA, bh.AngleFormat.DEGREES)',
      'gps = [sat for sat in sp3.satellites()',
      '       if sat.get_name().startswith("G")]',
      'r_epoch = {sat.get_name(): sat.state_ecef(EPOCH)[:3]',
      '           for sat in gps}',
      'enz = bh.relative_position_ecef_to_enz(',
      '    site_ecef, sat_ecef, bh.EllipsoidalConversionType.GEODETIC)',
      'az, el, _ = bh.position_enz_to_azel(',
      '    enz, bh.AngleFormat.DEGREES)',
    ],
  },
  tle: {
    needs: ['quick_hits'],
    lines: [
      'query = bh.celestrak.CelestrakQuery.gp.group(',
      '    "gps-ops").format(bh.celestrak.CelestrakOutputFormat.JSON)',
      'bh.celestrak.CelestrakClient(max_retries=0).download(',
      '    query, str(GP_CACHE))',
      '',
      'epochs = [EPOCH + t',
      '          for t in range(0, TRACK_SPAN_S + 1, TRACK_STEP_S)]',
      'for rec in records:',
      '    sat = bh.GPRecord.from_json(',
      '        json.dumps(rec)).to_sgp_propagator(TRACK_STEP_S)',
      '    r_itrf = np.array(sat.states_itrf(epochs))[:, :3]',
      '    lonlat = [bh.position_ecef_to_geodetic(',
      '        r, bh.AngleFormat.DEGREES)[:2] for r in r_itrf]',
    ],
  },
  propagate: {
    needs: ['quick_hits'],
    lines: [
      'def propagate(',
      '    x0: np.ndarray, force: bh.ForceModelConfig,',
      '    epochs: list[bh.Epoch]',
      ') -> bh.NumericalOrbitPropagator:',
      '    config = bh.NumericalPropagationConfig.with_method(',
      '        bh.IntegrationMethod.RKF78',
      '    ).with_abs_tol(1e-6).with_rel_tol(1e-12)',
      '    prop = bh.NumericalOrbitPropagator(',
      '        EPOCH, x0, config, force, SSO_PARAMS)',
      '    prop.propagate_to(epochs[-1])',
      '    return prop',
      'no_drag = bh.ForceModelConfig.default()',
      'no_drag.drag = None',
      'runs = {',
      '    "twobody": propagate(',
      '        x0, bh.ForceModelConfig.two_body(), epochs),',
      '    "full": propagate(',
      '        x0, bh.ForceModelConfig.default(), epochs),',
      '    "no_drag": propagate(x0, no_drag, epochs),',
      '}',
    ],
  },
  frames: {
    needs: ['quick_hits'],
    lines: [
      'sp3 = bh.SP3.from_file(str(path))',
      'sat = next(s for s in sp3.satellites()',
      '           if s.get_name() == f"G{FRAMES_PRN:02d}")',
      '',
      't0 = EPOCH - FRAMES_SPAN_S',
      'epochs = [t0 + t',
      '          for t in range(0, FRAMES_SPAN_S + 1, FRAMES_STEP_S)]',
      'return {',
      '    "eci_xyz_km":',
      '        np.array(sat.states_gcrf(epochs))[:, :3] / 1e3,',
      '    "ecef_xyz_km":',
      '        np.array(sat.states_itrf(epochs))[:, :3] / 1e3,',
      '}',
    ],
  },
};

Object.entries(CODE).forEach(([key, c]) => {
  figures[`code-${key}`] = { needs: c.needs, render: el => codeCard(el, c.lines, { ...c.opts, key }) };
});

/* ---------- cold open: GPS sky plot ---------- */
// Zenith at the center, horizon at the outer circle, north up, azimuth clockwise.
figures.skyplot = {
  needs: ['skyplot'],
  render(el, d) {
    const S = d.skyplot, svg = svgFor(el), W = el.offsetWidth, H = el.offsetHeight;
    const rad = Math.min(W, H) / 2 - 46, cx = W / 2, cy = H / 2;
    const to = (az, e) => { const r = rad * (90 - e) / 90, a = az * Math.PI / 180; return [cx + r * Math.sin(a), cy - r * Math.cos(a)]; };
    const grid = svgEl('g', {}, svg);
    [0, 90, 180, 270].forEach(az => { const [x, y] = to(az, 0); svgEl('line', { x1: cx, y1: cy, x2: x, y2: y, stroke: 'rgba(46,45,41,.15)', 'stroke-width': 1.5 }, grid); });
    [30, 60].forEach(e => svgEl('circle', { cx, cy, r: rad * (90 - e) / 90, fill: 'none', stroke: 'rgba(46,45,41,.22)', 'stroke-width': 1.5, 'stroke-dasharray': '4 6' }, grid));
    svgEl('circle', { cx, cy, r: rad * (90 - S.el_mask_deg) / 90, fill: 'none', stroke: 'rgba(140,21,21,.35)', 'stroke-width': 1.8, 'stroke-dasharray': '8 6' }, grid);
    svgEl('circle', { cx, cy, r: rad, fill: 'none', stroke: 'rgba(46,45,41,.55)', 'stroke-width': 2.4 }, grid);
    [['N', 0], ['E', 90], ['S', 180], ['W', 270]].forEach(([l, az]) => { const [x, y] = to(az, -11); text(grid, x, y + 8, l, { size: 24, anchor: 'middle', color: 'rgba(46,45,41,.6)', weight: 600 }); });
    [30, 60].forEach(e => text(grid, cx + 8, cy - rad * (90 - e) / 90 - 8, `${e}°`, { size: 22, color: 'rgba(46,45,41,.5)' }));
    const [mx, my] = to(225, S.el_mask_deg);
    text(grid, mx - 6, my + 26, `${fmt(S.el_mask_deg, 0)}° mask`, { size: 22, anchor: 'end', color: 'rgba(140,21,21,.7)' });

    const tracks = svgEl('g', {}, svg), marks = svgEl('g', {}, svg);
    el.__grid = grid;
    el.__tracks = S.sats.filter(s => s.track_azel_deg.length > 1).sort((a, b) => a.visible - b.visible).map(s =>
      exactPath(tracks, s.track_azel_deg.map(([a, e]) => to(a, e)), { color: s.visible ? C.lagunita : C.gray, width: s.visible ? 3 : 2, opacity: s.visible ? 0.6 : 0.45 }));
    el.__marks = [];
    S.sats.filter(s => s.el_deg >= 0 && !s.visible).forEach(s => {
      const [x, y] = to(s.az_deg, s.el_deg);
      el.__marks.push(svgEl('circle', { cx: x, cy: y, r: 6, fill: C.gray }, marks));
    });
    // Visible satellites: dot and PRN label, labels placed clear of other dots and labels.
    const vis = S.sats.filter(s => s.visible).sort((a, b) => b.el_deg - a.el_deg);
    const dots = vis.map(s => to(s.az_deg, s.el_deg));
    const placed = dots.map(([x, y]) => [x - 9, y - 9, x + 9, y + 9]);
    const lw = 44, lh = 22;
    vis.forEach((s, i) => {
      const [x, y] = dots[i];
      const g = svgEl('g', {}, marks);
      svgEl('circle', { cx: x, cy: y, r: 9, fill: C.lagunita }, g);
      const cands = [[14, -10, 'start'], [14, 26, 'start'], [-14, -10, 'end'], [-14, 26, 'end'], [0, -18, 'middle'], [0, 40, 'middle']];
      const boxOf = ([dx, dy, anc]) => { const x0 = anc === 'start' ? x + dx : anc === 'end' ? x + dx - lw : x - lw / 2; return [x0, y + dy - lh + 4, x0 + lw, y + dy + 4]; };
      const clear = b => placed.every(p => b[2] < p[0] || b[0] > p[2] || b[3] < p[1] || b[1] > p[3]);
      const pick = cands.find(c => clear(boxOf(c))) || cands[0];
      placed.push(boxOf(pick));
      text(g, x + pick[0], y + pick[1], prn(s.prn), { size: 22, anchor: pick[2], color: C.lagunita, weight: 600 });
      el.__marks.push(g);
    });
  },
  animate(el, d, s, A) {
    fadeIn(el.__grid, A, 0, 600);
    drawOnAnim(el.__tracks, A, 250, 1400, 45);
    el.__marks.forEach((m, i) => fadeIn(m, A, 1300 + i * 50, 500));
  },
};

/* ---------- tool families and the four properties ---------- */
// Each family is a row under the property cards (.prop-slot on the same slide): a check where the
// family tends to have the property, a gray dash where it tends not to, a gray word for "it depends".
const TOOL_FAMILIES = [
  { name: 'Commercial tools', eg: 'STK, FreeFlyer', has: ['yes', 'yes', 'no', 'no'] },
  { name: 'Research scripts and small packages', eg: 'university and personal projects', has: ['no', 'no', 'sometimes', 'yes'] },
  { name: 'Established open-source toolkits', eg: 'Orekit, GMAT', has: ['yes', 'sometimes', 'no', 'yes'] },
];

figures.tradeoff = {
  render(el) {
    const W = el.offsetWidth, rowH = 128, first = +(el.dataset.stepStart || 1);
    const cols = [...el.closest('section').querySelectorAll('.prop-slot')].map(c => c.offsetLeft + c.offsetWidth / 2 - el.offsetLeft);
    TOOL_FAMILIES.forEach((f, r) => {
      const row = document.createElement('div');
      row.className = 'tool-row';
      row.dataset.step = first + r;
      row.style.cssText = `position:absolute; left:0; top:${r * rowH}px; width:${W}px; height:${rowH}px;`;
      row.innerHTML = `<div class="tool-name">${f.name}</div><div class="tool-eg">${f.eg}</div>`;
      el.appendChild(row);
      const svg = svgFor(row), cy = 46, seed = hashSeed(f.name);
      f.has.forEach((h, i) => {
        const cx = cols[i];
        if (h === 'yes') strokePath(svg, roughPolyline([[cx - 18, cy], [cx - 5, cy + 14], [cx + 20, cy - 16]], { seed: seed + i, rough: 0.6 }), { color: C.ink, width: 4 });
        else if (h === 'no') strokePath(svg, roughLine(cx - 16, cy, cx + 16, cy, { seed: seed + i, rough: 0.5, passes: 1 }), { color: C.gray, width: 3 });
        else text(svg, cx, cy + 8, h, { size: 24, anchor: 'middle', color: C.gray, italic: true });
      });
    });
  },
};

/* ---------- module map ---------- */
// The overview of brahe's modules. Reused as a section divider: a slide with
// data-clone="Modules" data-lc-current="<key>[,<key>]" shows those cards in Cardinal, cards that
// were current on an earlier divider in gray, the rest in ink.
const MODULES = [
  { key: 'time', name: 'Time', sub: 'Epochs, UTC, GPS, TAI, TT' },
  { key: 'frames', name: 'Frames and coordinates', sub: 'GCRF, ITRF, geodetic, ENZ' },
  { key: 'orbits', name: 'Orbits', sub: 'Elements, TLE, Walker' },
  { key: 'propagation', name: 'Propagation', sub: 'SGP4, numerical, force models' },
  { key: 'access', name: 'Access', sub: 'Visibility windows, constraints' },
  { key: 'data', name: 'Data clients', sub: 'CelesTrak, Space-Track, IGS' },
  { key: 'estimation', name: 'Estimation', sub: 'EKF, UKF, batch least squares' },
];

function moduleIcon(svg, key, w, seed) {
  const cx = w / 2, R = (dd, col = C.ink, wd = 2.6) => strokePath(svg, dd, { color: col, width: wd });
  if (key === 'time') {
    R(roughEllipse(cx, 44, 34, 34, { seed, rough: 0.6 }));
    R(roughLine(cx, 44, cx, 20, { seed: seed + 1, passes: 1, rough: 0.4 }), C.ink, 3);
    R(roughLine(cx, 44, cx + 19, 52, { seed: seed + 2, passes: 1, rough: 0.4 }), C.ink, 3);
    svgEl('circle', { cx, cy: 44, r: 3.5, fill: C.ink }, svg);
  }
  if (key === 'frames') {
    const ox = cx - 34, oy = 74;
    R(roughArrow(ox, oy, ox + 62, oy, { seed, head: 10, rough: 0.5 }));
    R(roughArrow(ox, oy, ox, oy - 62, { seed: seed + 3, head: 10, rough: 0.5 }));
    const a = -0.5;
    R(roughArrow(ox, oy, ox + 62 * Math.cos(a), oy + 62 * Math.sin(a), { seed: seed + 6, head: 10, rough: 0.5 }), C.lagunita);
    R(roughArrow(ox, oy, ox + 62 * Math.sin(-a), oy - 62 * Math.cos(a), { seed: seed + 9, head: 10, rough: 0.5 }), C.lagunita);
  }
  if (key === 'orbits') {
    exactPath(svg, circlePts(cx, 44, 74, 26, -0.25, 120), { color: C.lagunita, width: 2.4 });
    R(roughEllipse(cx, 44, 17, 17, { seed, rough: 0.5 }));
    const [sx, sy] = circlePts(cx, 44, 74, 26, -0.25, 8)[1];
    svgEl('circle', { cx: sx, cy: sy, r: 5, fill: C.ink }, svg);
  }
  if (key === 'propagation') {
    const q = t => [cx - 76 + 152 * t, 76 - 70 * t + 22 * t * t];
    exactPath(svg, Array.from({ length: 41 }, (_, i) => q(i / 40)), { color: C.lagunita, width: 2.4 });
    [0, 0.33, 0.66].forEach(t => { const [x, y] = q(t); svgEl('circle', { cx: x, cy: y, r: 4.5, fill: C.ink }, svg); });
    const [ex, ey] = q(1), [px, py] = q(0.94);
    R(roughArrow(px, py, ex, ey, { seed, head: 12, rough: 0.4 }), C.lagunita, 2.4);
  }
  if (key === 'access') {
    R(roughLine(cx - 80, 80, cx + 80, 80, { seed, passes: 1 }), 'rgba(46,45,41,.6)', 2);
    R(roughPolyline([[cx - 52, 80], [cx - 40, 58], [cx - 28, 80]], { seed: seed + 1, rough: 0.4 }));
    svgEl('path', { d: `M${cx - 40} 58L${cx + 46} 20`, stroke: C.lagunita, 'stroke-width': 2.4, 'stroke-dasharray': '6 6', fill: 'none' }, svg);
    svgEl('circle', { cx: cx + 50, cy: 18, r: 6, fill: C.ink }, svg);
  }
  if (key === 'data') {
    const x0 = cx - 26, y0 = 34, dw = 52, dh = 50, f = 12;
    R(roughPolyline([[x0, y0], [x0 + dw - f, y0], [x0 + dw, y0 + f], [x0 + dw, y0 + dh], [x0, y0 + dh]], { seed, closed: true, rough: 0.5 }), C.ink, 2.4);
    [0, 1, 2].forEach(k => R(roughLine(x0 + 9, y0 + 20 + k * 10, x0 + dw - 9, y0 + 20 + k * 10, { seed: seed + 2 + k, passes: 1, rough: 0.3 }), 'rgba(46,45,41,.5)', 1.8));
    R(roughArrow(cx, 0, cx, 28, { seed: seed + 6, head: 10, rough: 0.4 }), C.lagunita, 2.4);
  }
  if (key === 'estimation') {
    const q = t => [cx - 76 + 152 * t, 74 - 52 * Math.sin(t * Math.PI * 0.9)];
    exactPath(svg, Array.from({ length: 41 }, (_, i) => q(i / 40)), { color: C.lagunita, width: 2.4 });
    [[0.1, 7], [0.28, -8], [0.46, 6], [0.64, -7], [0.82, 8]].forEach(([t, off], i) => {
      const [x, y0] = q(t), y = y0 + off;
      R(roughLine(x - 6, y - 6, x + 6, y + 6, { seed: seed + 10 + i, passes: 1, rough: 0.5 }), C.ink, 2.2);
      R(roughLine(x + 6, y - 6, x - 6, y + 6, { seed: seed + 20 + i, passes: 1, rough: 0.5 }), C.ink, 2.2);
    });
  }
}

figures.moduleMap = {
  render(el) {
    const n = MODULES.length, gap = 21, cw = (el.offsetWidth - gap * (n - 1)) / n;
    MODULES.forEach((m, i) => {
      const card = document.createElement('div');
      card.className = 'card mod-card';
      card.dataset.rough = 'box';
      card.dataset.roughKey = `mod-${m.key}`;
      card.dataset.lc = m.key;
      card.style.cssText = `left:${i * (cw + gap)}px; top:0; width:${cw}px; height:${el.offsetHeight}px;`;
      card.innerHTML = `<div class="icon"></div><h3>${m.name}</h3><p>${m.sub}</p>`;
      el.appendChild(card);
      const icon = card.querySelector('.icon');
      moduleIcon(svgFor(icon), m.key, icon.offsetWidth, hashSeed(m.key));
    });
  },
  animate(el, d, s, A) {
    if (el.classList.contains('cloned')) return;
    el.querySelectorAll('.mod-card').forEach((card, i) => {
      const o = { duration: 700, delay: 250 + i * 150, easing: EASE_IN, ...FILL };
      A.push(card.animate([{ opacity: 0, transform: 'translateY(28px)' }, { opacity: 1, transform: 'none' }], o));
      if (card.__roughPath) A.push(card.__roughPath.animate([{ opacity: 0 }, { opacity: 1 }], o));
    });
  },
};

/* ---------- quick hit: GPS ground tracks ---------- */
const splitLon = pts => { const out = []; let cur = []; pts.forEach((p, i) => { if (i && Math.abs(p[0] - pts[i - 1][0]) > 180) { out.push(cur); cur = []; } cur.push(p); }); out.push(cur); return out; };

figures.groundTracks = {
  needs: ['quick_hits', 'land', 'skyplot'],
  render(el, d) {
    const T = d.quick_hits.tle, svg = svgFor(el), W = el.offsetWidth, H = el.offsetHeight;
    const mw = Math.min(W, 2 * H), mh = mw / 2, ox = (W - mw) / 2, oy = (H - mh) / 2;
    const px = ([lon, lat]) => [ox + (lon + 180) / 360 * mw, oy + (90 - lat) / 180 * mh];
    el.__base = svgEl('g', {}, svg);
    strokePath(el.__base, roughRect(ox, oy, mw, mh, { seed: 4401, rough: 0.6 }), { color: 'rgba(46,45,41,.45)', width: 2 });
    d.land.rings.forEach(r => { if (r.length > 8) splitLon(r).forEach(seg => seg.length > 1 && exactPath(el.__base, seg.map(px), { color: 'rgba(46,45,41,.3)', width: 1.5 })); });
    svgEl('line', { x1: ox, x2: ox + mw, y1: oy + mh / 2, y2: oy + mh / 2, stroke: 'rgba(46,45,41,.18)', 'stroke-width': 1.5, 'stroke-dasharray': '4 6' }, el.__base);
    const trk = svgEl('g', {}, svg);
    el.__tracks = [];
    el.__starts = [];
    T.tracks.forEach(t => {
      splitLon(t.lonlat_deg).forEach(seg => seg.length > 1 && el.__tracks.push(exactPath(trk, seg.map(px), { color: C.lagunita, width: 3, opacity: 0.85 })));
      const [x, y] = px(t.lonlat_deg[0]);
      el.__starts.push(svgEl('circle', { cx: x, cy: y, r: 7, fill: C.lagunita }, trk));
    });
    const st = d.skyplot.station, [sx, sy] = px([st.lon_deg, st.lat_deg]);
    el.__site = svgEl('g', {}, svg);
    svgEl('circle', { cx: sx, cy: sy, r: 7, fill: C.ink }, el.__site);
    const lab = text(el.__site, sx + 12, sy - 12, 'Stanford', { size: 22, color: C.ink, weight: 600 });
    lab.setAttribute('stroke', C.board); lab.setAttribute('stroke-width', 6); lab.setAttribute('paint-order', 'stroke');
  },
  animate(el, d, s, A) {
    fadeIn(el.__base, A, 0, 600);
    el.__starts.forEach((c, i) => fadeIn(c, A, 300 + i * 60, 400));
    drawOnAnim(el.__tracks, A, 400, 1600, 0);
    fadeIn(el.__site, A, 600, 500);
  },
};

/* ---------- quick hit: what the force model changes ---------- */
// Position difference between propagations of the same initial state, log scale.
figures.forceModelEffect = {
  needs: ['quick_hits'],
  render(el, d) {
    const P = d.quick_hits.propagate;
    if (!P.dr_km || !P.dr_drag_km) { el.insertAdjacentHTML('beforeend', '<div class="pending">data pending: run scripts/quick_hits.py</div>'); return; }
    const svg = svgFor(el), days = P.t_h.map(t => t / 24);
    const late = (a) => a.filter((v, i) => P.t_h[i] >= 1 && v > 0);
    const lo = Math.pow(10, Math.floor(Math.log10(Math.min(...late(P.dr_km), ...late(P.dr_drag_km)))));
    const hi = Math.pow(10, Math.ceil(Math.log10(Math.max(...P.dr_km))));
    const ax = axes(svg, { left: 120, right: 40, top: 70, bottom: 80, xr: [0, last(days)], yr: [lo, hi], ylog: true, xlabel: 'days', ylabel: 'position difference (km, log scale)', xticks: niceTicks(0, last(days), 3), yfmt: v => pow10(Math.round(Math.log10(v))), seed: 4501 });
    const series = (vals) => vals.map((v, i) => [ax.x(days[i]), ax.y(Math.max(v, lo))]).filter((p, i) => vals[i] > 0);
    el.__axes = ax.g;
    el.__drag = exactPath(svg, series(P.dr_drag_km), { color: C.ink, width: 3 });
    el.__full = exactPath(svg, series(P.dr_km), { color: C.lagunita, width: 4.5 });
    const yFull = ax.y(last(P.dr_km)), yDrag = ax.y(Math.max(last(P.dr_drag_km), lo));
    const [lf, ld] = yDrag - yFull < 60 ? [yFull - 18, yDrag + 36] : [yFull - 18, yDrag - 18];
    el.__labels = svgEl('g', {}, svg);
    text(el.__labels, ax.box.x1, lf, 'two-body vs full force model', { size: 24, anchor: 'end', color: C.lagunita, weight: 600 });
    text(el.__labels, ax.box.x1, ld, 'effect of drag alone', { size: 24, anchor: 'end', color: C.ink });
  },
  animate(el, d, s, A) {
    if (!el.__full) return;
    fadeIn(el.__axes, A, 0, 600);
    drawOnAnim([el.__full, el.__drag], A, 300, 1600, 250);
    fadeIn(el.__labels, A, 1700, 500);
  },
};

/* ---------- quick hit: inertial and Earth-fixed frames ---------- */
// The same GPS orbit seen from above the North Pole, x and y components, same scale in both panels.
figures.eciVsEcef = {
  needs: ['quick_hits'],
  render(el, d) {
    const F = d.quick_hits.frames, svg = svgFor(el), W = el.offsetWidth, H = el.offsetHeight;
    const gap = 60, pw = (W - gap) / 2, top = 70;
    const rmax = Math.max(...F.eci_xyz_km.map(p => Math.hypot(p[0], p[1])), ...F.ecef_xyz_km.map(p => Math.hypot(p[0], p[1])));
    const k = Math.min(pw, H - top - 60) / 2 / rmax / 1.04;
    el.__paths = [];
    el.__base = svgEl('g', {}, svg);
    [['GCRF (inertial)', F.eci_xyz_km], ['ITRF (Earth-fixed)', F.ecef_xyz_km]].forEach(([title, xyz], i) => {
      const cx = i * (pw + gap) + pw / 2, cy = top + (H - top - 60) / 2;
      text(el.__base, cx, 30, title, { size: 30, anchor: 'middle', family: 'var(--serif)', weight: 600 });
      earth(el.__base, cx, cy, R_EARTH * k, 4600 + i);
      el.__paths.push(exactPath(svg, xyz.map(p => [cx + p[0] * k, cy - p[1] * k]), { color: C.lagunita, width: 3 }));
    });
    text(el.__base, W / 2, H - 14, 'seen from above the North Pole, same scale', { size: 22, anchor: 'middle', color: 'rgba(46,45,41,.6)' });
  },
  animate(el, d, s, A) {
    fadeIn(el.__base, A, 0, 600);
    drawOnAnim(el.__paths, A, 300, 2200, 0);
  },
};

/* ---------- title: the GPS constellation ---------- */
// Orthographic view of every GPS satellite's GCRF track over one orbital period. Behind-Earth
// parts of the tracks are drawn at 20% of the front opacity; dots replay the tracks in a loop that
// starts at the talk-time sample, one orbital period per GPS_LOOP_MS of wall time.
const GPS_LOOP_MS = 75000;

figures.gpsConstellation = {
  needs: ['gps_constellation'],
  render(el, d) {
    const G = d.gps_constellation, svg = svgFor(el), W = el.offsetWidth, H = el.offsetHeight;
    const nT = G.xyz_km.length, nS = G.prns.length;
    const rmax = Math.max(...G.xyz_km[0].map(p => Math.hypot(...p)));
    const cx = W / 2, cy = H / 2, kmPerPx = rmax / (Math.min(W, H) / 2 - 10);
    const proj = projector(cx, cy, kmPerPx, 20, 62), re = R_EARTH / kmPerPx;
    // Closed loop: the last sample repeats the first when the samples span the whole period.
    const closes = (nT - 1) * G.step_s >= G.period_s - 1;
    const nI = closes ? nT - 1 : nT;
    const pts = Array.from({ length: nS }, (_, s) => Array.from({ length: nI }, (_, t) => proj(G.xyz_km[t][s])));
    const back = svgEl('g', {}, svg);
    el.__earth = svgEl('g', {}, svg);
    earth(el.__earth, cx, cy, re, 5101);
    const front = svgEl('g', {}, svg), dots = svgEl('g', {}, svg);
    el.__paths = [];
    pts.forEach(track => frontBack([...track, track[0]], cx, cy, re).forEach(run => {
      if (run.pts.length > 1) el.__paths.push(exactPath(run.h ? back : front, run.pts, { color: C.lagunita, width: 2, opacity: run.h ? 0.07 : 0.35 }));
    }));
    el.__dots = pts.map(() => svgEl('circle', { r: 7, fill: C.lagunita }, dots));
    el.__dotLayer = dots;
    const t0 = G.talk_index ?? 0;
    el.__set = u => {
      const i = Math.floor(u) % nI, j = (i + 1) % nI, f = u - Math.floor(u);
      pts.forEach((track, s) => {
        const a = track[i], b = track[j], p = [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f];
        const dot = el.__dots[s];
        dot.setAttribute('cx', p[0].toFixed(1));
        dot.setAttribute('cy', p[1].toFixed(1));
        dot.setAttribute('opacity', hidden(p, cx, cy, re) ? 0.15 : 1);
      });
    };
    el.__nI = nI;
    el.__t0 = t0;
    el.__set(t0);
  },
  animate(el, d, s, A) {
    fadeIn(el.__earth, A, 0, 600);
    drawOnAnim(el.__paths, A, 200, 1600, 0);
    fadeIn(el.__dotLayer, A, 1500, 700);
    return loop(t => { el.__set((el.__t0 + t / GPS_LOOP_MS * el.__nI) % el.__nI); });
  },
};

/* ---------- check mark (brahe slide) ---------- */
// A hand-drawn check in Palo Verde that draws itself after data-delay ms.
figures.check = {
  render(el) {
    const svg = svgFor(el), w = el.offsetWidth, h = el.offsetHeight;
    el.__path = strokePath(svg, roughPolyline([[w * 0.2, h * 0.55], [w * 0.42, h * 0.85], [w * 0.82, h * 0.15]], { seed: hashSeed(el.dataset.state || 'check'), rough: 0.6 }), { color: C.green, width: 5 });
  },
  animate(el, d, s, A) { drawOnAnim([el.__path], A, +(el.dataset.delay || 0), 700); },
};

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
