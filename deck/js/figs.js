// Figures: every renderer draws from deck/data/*.json produced by scripts/*.py.
// Hand-drawn strokes (sketch.js) for frames, axes and diagrams; exact paths for orbits and data.
import { roughLine, roughRect, roughEllipse, roughArrow, roughPolyline, svgEl, strokePath, hashSeed, mulberry32 } from './sketch.js';

export const DATA_FILES = ['skyplot', 'quick_hits', 'land', 'gps_constellation', 'tle_vs_sp3', 'station_range', 'leo_receiver', 'mms_visibility', 'walker_pnt', 'gravity_crossover', 'benchmarks'];

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

// Polyline path data; a null entry ends a run and the next point starts a new one.
function linPath(pts) {
  let move = true;
  return pts.map(p => {
    if (!p) { move = true; return ''; }
    const cmd = move ? 'M' : 'L';
    move = false;
    return `${cmd}${p[0].toFixed(1)} ${p[1].toFixed(1)}`;
  }).join('');
}

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

// Run fn now, or on the click that reveals el when el or an ancestor carries data-step.
function whenShown(el, fn) {
  const host = el.closest('[data-step]');
  if (!host) { fn(); return () => {}; }
  return onStep(el, +host.dataset.step, fn);
}

const reducedMotion = () => matchMedia('(prefers-reduced-motion: reduce)').matches;

// Dim g to `op` while the slide is at `step` or later, in both directions of navigation.
function dimFromStep(el, g, step, op = 0.4) {
  el.closest('section').addEventListener('deckstep', e => {
    const to = e.detail.step >= step ? op : 1, from = +(g.getAttribute('opacity') ?? 1);
    g.setAttribute('opacity', to);
    if (e.detail.animate && from !== to && !reducedMotion()) g.animate([{ opacity: from }, { opacity: to }], { duration: 600, easing: EASE_IN });
  });
}

// SVG text with a board-colored halo so it stays legible over lines and fills.
function haloText(parent, x, y, str, opts) {
  const t = text(parent, x, y, str, opts);
  t.setAttribute('stroke', C.board); t.setAttribute('stroke-width', 6); t.setAttribute('paint-order', 'stroke');
  return t;
}

// Step line through (x, y) samples: hold each value until the next sample.
const stepPts = (xs, ys, X, Y) => xs.flatMap((x, i) => (i ? [[X(x), Y(ys[i - 1])], [X(x), Y(ys[i])]] : [[X(x), Y(ys[i])]]));

// Many points as one path of zero-length round-capped segments.
const dotsPath = pts => pts.map(([x, y]) => `M${x.toFixed(1)} ${y.toFixed(1)}l0 0`).join('');

// Vector helpers for 3D positions.
const dot3 = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const cross3 = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const unit3 = a => { const n = Math.hypot(...a); return a.map(v => v / n); };

// Pick label y positions near the targets, at least `gap` px apart.
function spreadLabels(ys, gap = 30) {
  const order = ys.map((y, i) => [y, i]).sort((a, b) => a[0] - b[0]), out = [];
  order.forEach(([y, i], k) => { out[i] = k ? Math.max(y, out[order[k - 1][1]] + gap) : y; });
  return out;
}

/* ======================= data bindings ======================= */

// Project facts shown on the brahe introduction slide.
const BRAHE = { since: 2014, license: 'MIT', core: 'Rust', bindings: 'Python' };

const PT_TIME = new Intl.DateTimeFormat('en-US', { timeZone: 'America/Los_Angeles', hour: 'numeric', minute: '2-digit' });
const PT_DATE = new Intl.DateTimeFormat('en-US', { timeZone: 'America/Los_Angeles', month: 'long', day: 'numeric', year: 'numeric' });
const last = a => a[a.length - 1];
const prn = n => `G${String(n).padStart(2, '0')}`;
const GP_SOURCE = { spacetrack: 'Space-Track', celestrak: 'CelesTrak' };
const UTC_DAY = new Intl.DateTimeFormat('en-US', { timeZone: 'UTC', month: 'long', day: 'numeric' });
const UTC_STAMP = iso => { const t = new Date(iso.endsWith('Z') ? iso : `${iso}Z`); return `${UTC_DAY.format(t)}, ${iso.slice(11, 16)} UTC`; };
const dateSpan = (a, b) => {
  const [ta, tb] = [new Date(a), new Date(b)];
  const sameMonth = ta.getUTCMonth() === tb.getUTCMonth();
  return `${UTC_DAY.format(ta)} to ${sameMonth ? tb.getUTCDate() : UTC_DAY.format(tb)}, ${tb.getUTCFullYear()}`;
};
// Latitudes where the Walker in-view curve crosses the GPS curve around the band where it is higher,
// by linear interpolation between grid latitudes.
function walkerBand(v) {
  const dlt = v.walker_mean.map((w, i) => w - v.gps_mean[i]), lat = v.lat_deg;
  const i0 = dlt.findIndex(x => x > 0), i1 = dlt.length - 1 - [...dlt].reverse().findIndex(x => x > 0);
  const cross = (a, b) => lat[a] + (lat[b] - lat[a]) * dlt[a] / (dlt[a] - dlt[b]);
  return [i0 > 0 ? cross(i0 - 1, i0) : lat[0], i1 < lat.length - 1 ? cross(i1, i1 + 1) : last(lat)];
}
const listAnd = a => (a.length < 3 ? a.join(' and ') : `${a.slice(0, -1).join(', ')} and ${last(a)}`);
// Minimum satellites for a position fix: the threshold behind the frac_time_4plus_* keys of mms_visibility.json.
const MIN_SATS = 4;
// Gravity timing quoted at the low end: the first swept degree of at least 10 (degree 2 is the overhead estimate).
const gravLow = G => Math.max(0, G.degrees.findIndex(n => n >= 10));
const signed = (v, d) => `${v < 0 ? '−' : '+'}${fmt(Math.abs(v), d)}`;
// Benchmark library names as written on the slide.
const LIB_NAMES = { brahe: 'brahe', orekit: 'Orekit', gmat: 'GMAT', nyx: 'Nyx', basilisk: 'Basilisk' };
const LANG_NAMES = { rust: 'Rust', python: 'Python' };
const libName = r => (r.library === 'brahe' ? `brahe ${LANG_NAMES[r.language] ?? r.language}` : LIB_NAMES[r.library] ?? r.library);
const isBraheRust = r => r.library === 'brahe' && r.language === 'rust';
const ratioFmt = v => (v < 1 ? fmt(v, 2) : v < 10 ? fmt(v, 1) : fmtInt(v));

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
  'tle.prn': d => prn(d.tle_vs_sp3.prn),
  'tle.norad': d => String(d.tle_vs_sp3.norad),
  'tle.source': d => GP_SOURCE[d.tle_vs_sp3.gp_source] ?? d.tle_vs_sp3.gp_source,
  'tle.epoch': d => UTC_STAMP(d.tle_vs_sp3.tle_epoch_utc),
  'tle.product': d => d.tle_vs_sp3.product.replace(/\.SP3(\.gz)?$/i, ''),
  'tle.span': d => fmt(d.tle_vs_sp3.span_h, 1),
  'tle.rms': d => fmt(d.tle_vs_sp3.rms_km, 2),
  'tle.max': d => fmt(d.tle_vs_sp3.max_km, 2),
  'range.prn': d => prn(d.station_range.prn),
  'range.dt': d => String(d.station_range.gps_minus_utc_s),
  'range.pos': d => fmt(d.station_range.pos_err_km, 1),
  'range.product': d => d.station_range.product.replace(/\.SP3(\.gz)?$/i, ''),
  'leo.rx': d => d.leo_receiver.receiver.name.split(' ')[0],
  'leo.alt': d => fmtInt(d.leo_receiver.receiver.alt_km),
  'leo.nLinks': d => String(d.leo_receiver.links_at_epoch.visible.filter(Boolean).length),
  'leo.mask': d => fmt(d.leo_receiver.el_mask_deg, 0),
  'leo.meanLeo': d => fmt(d.leo_receiver.mean_leo, 1),
  'leo.meanGround': d => fmt(d.leo_receiver.mean_ground, 1),
  'leo.minutes': d => fmt(last(d.leo_receiver.t_min), 0),
  'leo.stepS': d => fmt((d.leo_receiver.t_min[1] - d.leo_receiver.t_min[0]) * 60, 0),
  'leo.source': d => GP_SOURCE[d.leo_receiver.gp_source] ?? d.leo_receiver.gp_source,
  'leo.product': d => d.leo_receiver.product.replace(/\.SP3(\.gz)?$/i, ''),
  'mms.name': d => d.mms_visibility.object.name,
  'mms.source': d => GP_SOURCE[d.mms_visibility.gp_source] ?? d.mms_visibility.gp_source,
  'mms.span': d => dateSpan(...d.mms_visibility.span_utc),
  'mms.patternSource': d => d.mms_visibility.pattern.source,
  'mms.minSats': () => String(MIN_SATS),
  'mms.stepMin': d => fmt((d.mms_visibility.t_h[1] - d.mms_visibility.t_h[0]) * 60, 0),
  'mms.fracMain': d => fmt(100 * d.mms_visibility.frac_time_4plus_main, 1),
  'mms.fracSide': d => fmt(100 * d.mms_visibility.frac_time_4plus_with_side, 0),
  'walker.t': d => String(d.walker_pnt.config.t),
  'walker.p': d => String(d.walker_pnt.config.p),
  'walker.alt': d => fmtInt(d.walker_pnt.config.alt_km),
  'walker.inc': d => fmt(d.walker_pnt.config.inc_deg, 0),
  'walker.minutes': d => fmt(d.walker_pnt.span_h * 60, 0),
  'walker.force': d => d.walker_pnt.config.force_model.replace(/-/g, '\u2011'),
  'walker.integrator': d => d.walker_pnt.config.integrator,
  'walker.serial': d => fmt(d.walker_pnt.wall_s_serial, 2),
  'walker.parallel': d => fmt(d.walker_pnt.wall_s_parallel, 2),
  'walker.threads': d => String(d.walker_pnt.threads),
  'walker.speedup': d => fmt(d.walker_pnt.speedup, 1),
  'walker.source': d => d.walker_pnt.config.source,
  'walker.crossLo': d => fmt(walkerBand(d.walker_pnt.in_view)[0], 0),
  'walker.crossHi': d => fmt(walkerBand(d.walker_pnt.in_view)[1], 0),
  'walker.eqW': d => fmt(d.walker_pnt.in_view.walker_mean[0], 1),
  'walker.eqG': d => fmt(d.walker_pnt.in_view.gps_mean[0], 1),
  'walker.topLat': d => fmt(last(d.walker_pnt.in_view.lat_deg), 0),
  'walker.topW': d => fmt(last(d.walker_pnt.in_view.walker_mean), 1),
  'walker.topG': d => fmt(last(d.walker_pnt.in_view.gps_mean), 1),
  'grav.model': d => d.gravity_crossover.model,
  'grav.maxDeg': d => String(last(d.gravity_crossover.degrees)),
  'grav.kernel': d => d.gravity_crossover.kernel,
  'grav.integrator': d => d.gravity_crossover.integrator,
  'grav.passes': d => String(d.gravity_crossover.passes),
  'grav.repeats': d => String(d.gravity_crossover.repeats_per_pass),
  'grav.cpu': d => d.gravity_crossover.machine.cpu,
  'grav.threads': d => String(d.gravity_crossover.machine.threads),
  'grav.load': d => fmt((d.gravity_crossover.machine.load_avg_1min_start + d.gravity_crossover.machine.load_avg_1min_end) / 2, 1),
  'grav.threshold': d => String(d.gravity_crossover.auto_threshold_nmax),
  'grav.overhead': d => fmt(d.gravity_crossover.overhead_us_degree2, 1),
  'grav.range': d => { const r = d.gravity_crossover.crossover_range_nmax; return r ? `${r[0]} to ${r[1]}` : undefined; },
  'grav.lowN': d => String(d.gravity_crossover.degrees[gravLow(d.gravity_crossover)]),
  'grav.lowSerial': d => fmt(d.gravity_crossover.serial_us[gravLow(d.gravity_crossover)], 1),
  'grav.lowParallel': d => fmt(d.gravity_crossover.parallel_us[gravLow(d.gravity_crossover)], 1),
  'grav.topN': d => String(last(d.gravity_crossover.degrees)),
  'grav.topSerial': d => fmt(last(d.gravity_crossover.serial_us), 1),
  'grav.topParallel': d => fmt(last(d.gravity_crossover.parallel_us), 1),
  'bench.version': d => d.benchmarks.brahe_version,
  'bench.date': d => PT_DATE.format(new Date(d.benchmarks.benchmark_run_utc)),
  'bench.statistic': d => d.benchmarks.statistic,
  'bench.libs': d => listAnd([...new Set(d.benchmarks.tasks.flatMap(t => t.results.filter(r => r.library !== 'brahe').map(libName)))]),
  'pr.prn': d => prn(d.station_range.prn),
  'pr.geo': d => fmt(d.station_range.terms_m.geometric, 2),
  'pr.light': d => signed(d.station_range.terms_m.light_time, 2),
  'pr.earth': d => signed(d.station_range.terms_m.earth_rotation, 2),
  'pr.clock': d => signed(d.station_range.terms_m.sat_clock, 2),
  'dop.skipW': d => fmtInt(d.walker_pnt.dop.skipped.walker),
  'dop.skipG': d => fmtInt(d.walker_pnt.dop.skipped.gps),
  'dop.total': d => fmtInt(d.walker_pnt.dop.samples_per_lat * d.walker_pnt.dop.lat_deg.length),
  'dop.perLat': d => fmtInt(d.walker_pnt.dop.samples_per_lat),
  'dop.mask': d => fmt(d.walker_pnt.in_view.el_mask_deg, 0),
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
//   lines      source lines, one string per line ('' for a blank line, drawn at half height)
//   highlight  line matches drawn in Cardinal; [match, step] turns that line Cardinal on click `step`
//   steps      {match: step}: the line stays hidden until that click
//   marks      [[match, 'text', 'cardinal' | 'green']]: that text on the line drawn in the color
//   size       font size in px (22 minimum)
//   key        seed for the hand-drawn box, so clones redraw the same outline
// A match selects the first line that contains it as a substring.
function markedHTML(line, mark) {
  const i = mark ? line.indexOf(mark[1]) : -1;
  if (i < 0) return pyHTML(line);
  const j = i + mark[1].length;
  return `${pyHTML(line.slice(0, i))}<span class="tok tok-${mark[2]}">${pyHTML(line.slice(i, j))}</span>${pyHTML(line.slice(j))}`;
}

function codeCard(el, lines, { highlight = [], steps = {}, marks = [], size = 22, key = '' } = {}) {
  const box = document.createElement('div');
  box.className = 'code-card';
  box.dataset.rough = 'box';
  box.dataset.roughKey = `code-${key || lines[0]}`;
  box.style.fontSize = `${Math.max(22, size)}px`;
  const pre = document.createElement('pre');
  const lineOf = match => lines.findIndex(ln => ln.includes(match));
  const hl = new Map(highlight.map(h => (Array.isArray(h) ? [lineOf(h[0]), h[1]] : [lineOf(h), 0])));
  const stepAt = new Map(Object.entries(steps).map(([m, k]) => [lineOf(m), k]));
  lines.forEach((ln, i) => {
    const row = document.createElement('div');
    row.className = ln ? 'ln' : 'ln blank';
    row.innerHTML = markedHTML(ln, marks.find(m => lineOf(m[0]) === i)) || '​';
    if (hl.get(i) === 0) row.classList.add('hl');
    else if (hl.has(i)) {
      const over = document.createElement('span');
      over.className = 'ln-hl';
      over.textContent = ln;
      over.dataset.step = hl.get(i);
      row.appendChild(over);
    }
    if (stepAt.has(i)) row.dataset.step = stepAt.get(i);
    pre.appendChild(row);
  });
  box.appendChild(pre);
  el.appendChild(box);
  return box;
}

// Code shown on slides: the complete programs in deck/snippets/<file>.py, loaded when the deck
// starts. A card shows the file below its PEP 723 header and the blank line after it, verbatim.
// `from`/`to` (line matches) show part of a file on one card when a program spans two cards.
// Each entry becomes the figure `code-<key>` (use <div class="fig" data-fig="code-<key>">); a
// snippet file that fails to load shows a pending note.
const CODE = {
  skyplot: { file: 'skyplot' },
  tle: { file: 'ground_tracks' },
  propagate: { file: 'force_model' },
  frames: { file: 'frames' },
  tleSp3: { file: 'tle_vs_sp3' },
  rangeEpochs: { file: 'gps_time_as_utc', opts: { marks: [['correct = bh.Epoch(', 'bh.GPS', 'green'], ['mistaken = bh.Epoch(', 'bh.UTC', 'cardinal']] } },
  leoReceiver: { file: 'leo_receiver', opts: { marks: [['n_iss = gps_in_view(', 'iss.state_itrf(epoch)[:3]', 'cardinal']] } },
  walker: { file: 'walker' },
  valueEvent: { file: 'value_event' },
  additionalDynamics: { file: 'battery' },
  sensitivity: { file: 'sensitivity' },
  propertyComputer: { file: 'property_computer', to: 't0 = bh.Epoch(' },
  propertyAccess: { file: 'property_computer', from: 't0 = bh.Epoch(' },
};

const snippetBody = src => {
  const lines = src.replace(/\r\n/g, '\n').split('\n');
  const close = lines.findIndex((ln, i) => i > 0 && ln === '# ///');
  const body = lines.slice(close + 1);
  if (body[0] === '') body.shift();
  while (body.length && body[body.length - 1] === '') body.pop();
  return body;
};

const SNIPPETS = Object.fromEntries(await Promise.all([...new Set(Object.values(CODE).map(c => c.file))].map(async file => {
  try {
    const r = await fetch(`snippets/${file}.py`, { cache: 'no-cache' });
    return [file, r.ok ? snippetBody(await r.text()) : null];
  } catch { return [file, null]; }
})));

function snippetLines({ file, from, to }) {
  let lines = SNIPPETS[file];
  if (!lines) return null;
  const at = m => lines.findIndex(ln => ln.includes(m));
  lines = lines.slice(from ? at(from) : 0, to ? at(to) : lines.length);
  while (lines.length && !lines[0]) lines = lines.slice(1);
  while (lines.length && !lines[lines.length - 1]) lines = lines.slice(0, -1);
  return lines;
}

Object.entries(CODE).forEach(([key, c]) => {
  figures[`code-${key}`] = {
    needs: [],
    render(el) {
      const lines = snippetLines(c);
      if (!lines) { el.insertAdjacentHTML('beforeend', `<div class="pending">snippet pending: deck/snippets/${c.file}.py</div>`); return; }
      codeCard(el, lines, { ...c.opts, key });
    },
  };
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
    // Samples at or above lo, in pixels; where the curve crosses lo it is cut at the crossing,
    // interpolated in (days, log10 value), and samples below lo are left out.
    const series = (vals) => vals.flatMap((v, i) => {
      const inside = v >= lo, prev = vals[i - 1], pts = [];
      if (i && inside !== prev >= lo && v > 0 && prev > 0) {
        const f = (Math.log10(lo) - Math.log10(prev)) / (Math.log10(v) - Math.log10(prev));
        pts.push([ax.x(days[i - 1] + f * (days[i] - days[i - 1])), ax.y(lo)]);
      }
      if (inside) pts.push([ax.x(days[i]), ax.y(v)]);
      else if (i && prev >= lo) pts.push(null);
      return pts;
    });
    el.__axes = ax.g;
    el.__drag = exactPath(svg, series(P.dr_drag_km), { color: C.ink, width: 3 });
    el.__full = exactPath(svg, series(P.dr_km), { color: C.lagunita, width: 4.5 });
    const yFull = ax.y(last(P.dr_km)), yDrag = ax.y(last(P.dr_drag_km));
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
      if (run.pts.length > 1) el.__paths.push(exactPath(run.h ? back : front, run.pts, { color: C.lagunita, width: 1.6, opacity: run.h ? 0.06 : 0.3 }));
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

/* ---------- Act 3: public TLE against the IGS orbit ---------- */
// SGP4 from the public GP element set minus the IGS ultra-rapid orbit, in the RTN frame of the IGS
// orbit. Along-track is the highlighted series; labels sit at the line ends.
figures.tleVsSp3 = {
  needs: ['tle_vs_sp3'],
  render(el, d) {
    const T = d.tle_vs_sp3, D = T.diff_rtn_km, svg = svgFor(el);
    const all = [...D.R, ...D.T, ...D.N];
    const lo = Math.min(0, Math.floor(Math.min(...all) * 2) / 2), hi = Math.ceil(Math.max(...all));
    const xr = [T.t_h[0], last(T.t_h)];
    const ax = axes(svg, { left: 100, right: 170, top: 20, bottom: 80, xr, yr: [lo, hi], xlabel: 'hours from the talk time', ylabel: 'TLE minus IGS orbit (km)', xticks: niceTicks(...xr, 5), yticks: niceTicks(lo, hi, 5).filter(v => v >= lo), seed: 6101 });
    svgEl('line', { x1: ax.box.x0, x2: ax.box.x1, y1: ax.y(0), y2: ax.y(0), stroke: 'rgba(46,45,41,.25)', 'stroke-width': 1.5, 'stroke-dasharray': '4 6' }, ax.g);
    const series = [['radial', D.R, C.ink, 3], ['cross-track', D.N, C.gray, 3], ['along-track', D.T, C.cardinal, 4.5]];
    el.__paths = series.map(([, v, color, width]) => exactPath(svg, v.map((y, i) => [ax.x(T.t_h[i]), ax.y(y)]), { color, width }));
    const ly = spreadLabels(series.map(([, v]) => ax.y(last(v)) + 8), 30);
    el.__labels = svgEl('g', {}, svg);
    series.forEach(([name, , color], i) => text(el.__labels, ax.box.x1 + 14, ly[i], name, { size: 24, color, weight: color === C.cardinal ? 600 : 400 }));
  },
  animate(el, d, s, A) {
    return whenShown(el, () => {
      drawOnAnim(el.__paths, A, 150, 1400, 200);
      fadeIn(el.__labels, A, 1300, 500);
    });
  },
};

/* ---------- Act 3: GPS time read as UTC ---------- */
// Range error over the pass when the epoch is labeled UTC instead of GPS time, with its largest value.
figures.rangeMistake = {
  needs: ['station_range'],
  render(el, d) {
    const S = d.station_range, E = S.range_err_km, svg = svgFor(el);
    const lo = Math.floor(Math.min(0, ...E) / 5) * 5, hi = Math.ceil(Math.max(0, ...E) / 5) * 5;
    const xr = [S.t_h[0], last(S.t_h)];
    const ax = axes(svg, { left: 100, right: 40, top: 40, bottom: 80, xr, yr: [lo, hi], xlabel: `hours, over the pass of ${prn(S.prn)} above Stanford`, ylabel: 'range error (km)', xticks: niceTicks(...xr, 6), yticks: niceTicks(lo, hi, 5), seed: 6201 });
    svgEl('line', { x1: ax.box.x0, x2: ax.box.x1, y1: ax.y(0), y2: ax.y(0), stroke: 'rgba(46,45,41,.25)', 'stroke-width': 1.5, 'stroke-dasharray': '4 6' }, ax.g);
    el.__path = exactPath(svg, E.map((y, i) => [ax.x(S.t_h[i]), ax.y(y)]), { color: C.cardinal, width: 4.5 });
    const k = E.reduce((b, v, i) => (Math.abs(v) > Math.abs(E[b]) ? i : b), 0), px = ax.x(S.t_h[k]), py = ax.y(E[k]);
    el.__max = svgEl('g', {}, svg);
    svgEl('circle', { cx: px, cy: py, r: 8, fill: C.cardinal }, el.__max);
    const right = px > (ax.box.x0 + ax.box.x1) / 2;
    haloText(el.__max, px + (right ? -16 : 16), py + (E[k] > 0 ? -16 : 34), `largest: ${fmt(Math.abs(E[k]), 1)} km`, { size: 26, color: C.cardinal, weight: 600, anchor: right ? 'end' : 'start' });
  },
  animate(el, d, s, A) {
    return whenShown(el, () => {
      drawOnAnim([el.__path], A, 150, 1500);
      fadeIn(el.__max, A, 1500, 500);
    });
  },
};

/* ---------- Act 3: receiver on the ISS ---------- */
// Orthographic view at the talk time, to scale: the ISS orbit (GCRF), every GPS satellite, and a
// line of sight from the ISS to each GPS satellite it sees. Behind-Earth runs are drawn at 20%.
figures.leoLinks = {
  needs: ['leo_receiver'],
  render(el, d) {
    const L = d.leo_receiver, K = L.links_at_epoch, svg = svgFor(el), W = el.offsetWidth, H = el.offsetHeight;
    const rmax = Math.max(...K.gps_xyz_km.map(p => Math.hypot(...p)));
    const cx = W / 2, cy = H / 2, kmPerPx = rmax / (Math.min(W, H) / 2 - 16), re = R_EARTH / kmPerPx;
    // Choose the view so the ISS orbit opens into an ellipse (about 55 degrees from edge-on) and
    // the ISS sits on the near side of the Earth, off center.
    const hN = unit3(cross3(L.orbit_xyz_km[0], L.orbit_xyz_km[1])), rxU = unit3(K.rx_xyz_km);
    let best = [0, 0, Infinity];
    for (let yw = 0; yw < 360; yw += 2) for (let tl = -60; tl <= 60; tl += 2) {
      const y = yw * Math.PI / 180, t = tl * Math.PI / 180, dir = [Math.sin(y) * Math.cos(t), Math.cos(y) * Math.cos(t), -Math.sin(t)];
      const cost = (Math.abs(dot3(dir, hN)) - 0.8) ** 2 + (dot3(dir, rxU) + 0.45) ** 2 + 0.02 * (tl / 60) ** 2;
      if (cost < best[2]) best = [yw, tl, cost];
    }
    const proj = projector(cx, cy, kmPerPx, best[0], best[1]);
    const back = svgEl('g', {}, svg);
    el.__earth = svgEl('g', {}, svg);
    earth(el.__earth, cx, cy, re, 6301);
    const front = svgEl('g', {}, svg);
    const runs = (pts, opts, behindOp) => frontBack(pts.map(proj), cx, cy, re).filter(r => r.pts.length > 1)
      .map(r => exactPath(r.h ? back : front, r.pts, { ...opts, opacity: r.h ? behindOp : opts.opacity ?? 1 }));
    el.__orbit = runs(L.orbit_xyz_km, { color: C.lagunita, width: 3 }, 0.2);
    const rx = K.rx_xyz_km;
    el.__links = K.gps_xyz_km.filter((_, j) => K.visible[j]).map(g =>
      runs(Array.from({ length: 41 }, (_, i) => rx.map((v, c) => v + (g[c] - v) * i / 40)), { color: C.lagunita, width: 2, opacity: 0.7 }, 0.14));
    el.__dots = svgEl('g', {}, svg);
    K.gps_xyz_km.forEach((g, j) => {
      const p = proj(g), vis = K.visible[j];
      svgEl('circle', { cx: p[0], cy: p[1], r: vis ? 9 : 6, fill: vis ? C.lagunita : C.gray, opacity: hidden(p, cx, cy, re) ? 0.25 : 1 }, el.__dots);
    });
    const r = proj(rx);
    el.__rx = svgEl('g', {}, svg);
    svgEl('circle', { cx: r[0], cy: r[1], r: 9, fill: C.ink, stroke: C.board, 'stroke-width': 3 }, el.__rx);
    haloText(el.__rx, r[0] + 16, r[1] + 30, L.receiver.name.split(' ')[0], { size: 26, weight: 600 });
  },
  animate(el, d, s, A) {
    fadeIn(el.__earth, A, 0, 600);
    drawOnAnim(el.__orbit, A, 200, 1000, 0);
    fadeIn(el.__rx, A, 700, 400);
    fadeIn(el.__dots, A, 700, 500);
    el.__links.forEach((ls, i) => drawOnAnim(ls, A, 1000 + i * 70, 600, 0));
  },
};

// GPS satellites in view against time for the ground station and the ISS, step lines with dashed
// means. The ISS series appears on click 1 and the ground series dims.
figures.leoCounts = {
  needs: ['leo_receiver'],
  render(el, d) {
    const L = d.leo_receiver, svg = svgFor(el), t = L.t_min;
    const hi = Math.max(...L.n_visible_leo, ...L.n_visible_ground) + 1;
    const ax = axes(svg, { left: 100, right: 300, top: 30, bottom: 80, xr: [0, last(t)], yr: [0, hi], xlabel: 'minutes from the talk time', ylabel: `GPS satellites above ${fmt(L.el_mask_deg, 0)}° elevation`, xticks: niceTicks(0, last(t), 5), yticks: niceTicks(0, hi, 4), seed: 6401 });
    const series = [['Stanford', L.n_visible_ground, L.mean_ground, C.ink], [L.receiver.name.split(' ')[0], L.n_visible_leo, L.mean_leo, C.lagunita]];
    const ly = spreadLabels(series.map(([, , m]) => ax.y(m) + 8), 34);
    el.__groups = series.map(([name, n, mean, color], i) => {
      const g = svgEl('g', i ? { 'data-step': 1 } : {}, svg);
      const path = exactPath(g, stepPts(t, n, ax.x, ax.y), { color, width: i ? 3.5 : 3 });
      svgEl('line', { x1: ax.box.x0, x2: ax.box.x1, y1: ax.y(mean), y2: ax.y(mean), stroke: color, 'stroke-width': 2, 'stroke-dasharray': '8 7', opacity: 0.8 }, g);
      text(g, ax.box.x1 + 16, ly[i], `${name}, mean ${fmt(mean, 1)}`, { size: 26, color, weight: 600 });
      g.__path = path;
      return g;
    });
    dimFromStep(el, el.__groups[0], 1, 0.4);
  },
  animate(el, d, s, A) {
    drawOnAnim([el.__groups[0].__path], A, 200, 1400);
    return onStep(el, 1, () => drawOnAnim([el.__groups[1].__path], A, 100, 1400));
  },
};

/* ---------- Act 3: MMS above the GPS constellation ---------- */
// The MMS 1 orbit seen face-on in its own plane (GCRF), to scale, apogee to the left; the GPS orbit
// radius as an exact circle; one GPS satellite opposite the apogee with its main-lobe and side-lobe
// half angles drawn exactly from the pattern, and the shadow of the Earth plus mask altitude.
// Click 1 starts a replay of MMS along the orbit; the slide's [data-readout] fields show the
// distance and the main-lobe and main-plus-side-lobe counts for the current sample. Stepping back
// to step 0 stops the replay and returns MMS to the first sample.
const MMS_LOOP_MS = 16000;

figures.mmsOrbit = {
  needs: ['mms_visibility'],
  render(el, d) {
    const M = d.mms_visibility, P = M.pattern, O = M.orbit_xyz_km, svg = svgFor(el), W = el.offsetWidth, H = el.offsetHeight;
    const n = O.length, kApo = M.t_h.indexOf(M.apogee_t_h);
    const h = unit3(O.slice(1).reduce((acc, p, i) => cross3(O[i], p).map((v, c) => acc[c] + v), [0, 0, 0]));
    const e1 = unit3(O[kApo]), e2 = cross3(h, e1);
    const uv = O.map(p => [dot3(p, e1), dot3(p, e2)]);
    const gR = M.gps_radius_km, umax = Math.max(...uv.map(q => q[0])), umin = Math.min(-gR, ...uv.map(q => q[0]));
    const vmax = Math.max(gR, ...uv.map(q => Math.abs(q[1]))), pad = 30;
    const k = Math.max((umax - umin) / (W - 2 * pad), 2 * vmax / (H - 2 * pad));
    const ox = pad + umax / k, oy = H / 2, to = ([u, v]) => [ox - u / k, oy - v / k];
    const clipId = `clip-${Math.random().toString(36).slice(2)}`;
    svgEl('rect', { x: 0, y: 0, width: W, height: H }, svgEl('clipPath', { id: clipId }, svgEl('defs', {}, svg)));

    // One GPS satellite on the far side of the Earth from the apogee, boresight toward the Earth.
    const G = to([-gR, 0]), L = 4 * W, ray = a => [G[0] - L * Math.cos(a), G[1] - L * Math.sin(a)];
    const aMain = P.main_half_angle_deg * Math.PI / 180, aSide = P.side_lobe_max_deg * Math.PI / 180;
    const rm = R_EARTH + P.earth_mask_alt_km, ab = Math.asin(rm / gR), tl = Math.sqrt(gR * gR - rm * rm) / k;
    const tp = a => [G[0] - tl * Math.cos(a), G[1] - tl * Math.sin(a)];
    const poly = (pts, attrs, parent) => svgEl('path', { d: `${linPath(pts)}Z`, ...attrs }, parent);
    el.__cones = svgEl('g', { 'clip-path': `url(#${clipId})` }, svg);
    poly([G, ray(aSide), ray(aMain)], { fill: C.sky, opacity: 0.1 }, el.__cones);
    poly([G, ray(-aMain), ray(-aSide)], { fill: C.sky, opacity: 0.1 }, el.__cones);
    poly([G, ray(aMain), ray(-aMain)], { fill: C.sky, opacity: 0.2 }, el.__cones);
    poly([tp(ab), ray(ab), ray(-ab), tp(-ab)], { fill: C.board }, el.__cones);
    [aSide, -aSide].forEach(a => exactPath(el.__cones, [G, ray(a)], { color: C.lagunita, width: 1.8, opacity: 0.45 }));
    [aMain, -aMain].forEach(a => exactPath(el.__cones, [G, ray(a)], { color: C.lagunita, width: 2.2, opacity: 0.8 }));

    el.__shell = exactPath(svg, circlePts(ox, oy, gR / k, gR / k, 0, 180), { color: C.ink, width: 2, opacity: 0.55 });
    svgEl('circle', { cx: ox, cy: oy, r: R_EARTH / k, fill: C.board }, svg);
    el.__earth = earth(svg, ox, oy, R_EARTH / k, 6501);
    el.__orbit = exactPath(svg, uv.map(to), { color: C.lagunita, width: 3.5 });

    el.__labels = svgEl('g', {}, svg);
    svgEl('circle', { cx: G[0], cy: G[1], r: 7, fill: C.ink }, el.__labels);
    haloText(el.__labels, G[0] + 4, G[1] + 40, 'one GPS satellite', { size: 22, anchor: 'middle', color: C.ink });
    haloText(el.__labels, ox, oy - gR / k - 12, 'GPS orbit radius', { size: 22, anchor: 'middle', color: 'rgba(46,45,41,.7)' });
    const lab = (a, dist, str, dy) => { const [x, y] = [G[0] - dist * Math.cos(a), G[1] - dist * Math.sin(a)]; haloText(el.__labels, x, y + dy, str, { size: 24, anchor: 'end', color: C.lagunita, weight: 600 }); };
    lab(aMain, 0.62 * (G[0] - pad), `main lobe, ${fmt(P.main_half_angle_deg, 1)}°`, -14);
    lab(aSide, 0.9 * (G[1] - pad) / Math.sin(aSide), `side lobes to ${fmt(P.side_lobe_max_deg, 0)}°`, 6);
    haloText(el.__labels, G[0] - 0.62 * (G[0] - pad), oy - 12, 'blocked by the Earth', { size: 22, anchor: 'middle', color: 'rgba(46,45,41,.6)' });
    const [apoX, apoY] = to(uv[kApo]);
    haloText(el.__labels, apoX + 6, apoY + 44, M.object.name, { size: 26, color: C.lagunita, weight: 600 });

    el.__mms = svgEl('circle', { r: 11, fill: C.lagunita, stroke: C.board, 'stroke-width': 3 }, svg);
    const sec = el.closest('section'), out = {};
    sec.querySelectorAll('[data-readout]').forEach(f => { out[f.dataset.readout] = f; });
    let shown = -1;
    el.__set = i => {
      if (i === shown) return;
      shown = i;
      const [x, y] = to(uv[i]);
      el.__mms.setAttribute('cx', x.toFixed(1));
      el.__mms.setAttribute('cy', y.toFixed(1));
      if (out.r) out.r.textContent = fmt(M.radius_re[i], 1);
      if (out.main) out.main.textContent = String(M.n_main[i]);
      if (out.side) out.side.textContent = String(M.n_side[i]);
    };
    el.__n = n;
    el.__kApo = kApo;
    el.__set(kApo);
  },
  animate(el, d, s, A) {
    const sec = el.closest('section');
    fadeIn(el.__cones, A, 0, 700);
    fadeIn(el.__earth, A, 0, 600);
    drawOnAnim([el.__shell], A, 200, 1100);
    drawOnAnim([el.__orbit], A, 500, 1500);
    fadeIn(el.__labels, A, 1400, 500);
    let stop = null;
    const start = () => { stop?.(); stop = loop(t => el.__set(Math.floor((t / MMS_LOOP_MS % 1) * el.__n))); };
    const reset = () => { stop?.(); stop = null; el.__set(0); };
    if ((sec.__step || 0) >= 1) start(); else reset();
    const off = onStep(el, 1, start);
    const back = e => { if (e.detail.step < 1) reset(); };
    sec.addEventListener('deckstep', back);
    return () => { off(); sec.removeEventListener('deckstep', back); stop?.(); };
  },
};

// GPS satellites usable by MMS against its distance from Earth's center, one dot per sample over the
// orbit: main lobe first, main plus side lobes on click 1 (main lobe dims).
figures.mmsCounts = {
  needs: ['mms_visibility'],
  render(el, d) {
    const M = d.mms_visibility, svg = svgFor(el);
    const xr = [0, Math.ceil(Math.max(...M.radius_re) / 5) * 5], hi = Math.ceil((Math.max(...M.n_side) + 1) / 5) * 5;
    const ax = axes(svg, { left: 100, right: 40, top: 30, bottom: 80, xr, yr: [0, hi], xlabel: 'distance from Earth\'s center (Earth radii)', ylabel: 'usable GPS satellites', xticks: niceTicks(...xr, 6), yticks: niceTicks(0, hi, 6), seed: 6601 });
    const gx = ax.x(M.gps_radius_km / R_EARTH);
    const ref = svgEl('g', {}, svg);
    svgEl('line', { x1: gx, x2: gx, y1: ax.box.y0, y2: ax.box.y1, stroke: 'rgba(46,45,41,.4)', 'stroke-width': 2, 'stroke-dasharray': '6 7' }, ref);
    haloText(ref, gx + 10, ax.box.y1 + 20, 'GPS orbit radius', { size: 22, color: 'rgba(46,45,41,.7)' });
    svgEl('line', { x1: ax.box.x0, x2: ax.box.x1, y1: ax.y(MIN_SATS), y2: ax.y(MIN_SATS), stroke: 'rgba(46,45,41,.45)', 'stroke-width': 2, 'stroke-dasharray': '6 7' }, ref);
    haloText(ref, ax.box.x1, ax.y(MIN_SATS) - 10, `${MIN_SATS} satellites`, { size: 22, anchor: 'end', color: 'rgba(46,45,41,.7)' });
    const pts = n => M.radius_re.map((r, i) => [ax.x(r), ax.y(n[i])]);
    el.__side = svgEl('g', { 'data-step': 1 }, svg);
    const ring = svgEl('g', { fill: 'none', stroke: C.lagunita, 'stroke-width': 1.6, opacity: 0.45 }, el.__side);
    pts(M.n_side).forEach(([x, y]) => svgEl('circle', { cx: x.toFixed(1), cy: y.toFixed(1), r: 4.5 }, ring));
    haloText(el.__side, ax.x(xr[1]) - 6, ax.y(Math.max(...M.n_side)) - 14, 'main or side lobes', { size: 24, anchor: 'end', color: C.lagunita });
    el.__main = svgEl('g', {}, svg);
    svgEl('path', { d: dotsPath(pts(M.n_main)), stroke: C.lagunita, 'stroke-width': 8, 'stroke-linecap': 'round', fill: 'none', opacity: 0.7 }, el.__main);
    haloText(el.__main, ax.x(xr[1]) - 6, ax.y(MIN_SATS) + 34, 'main lobe', { size: 24, anchor: 'end', color: C.lagunita, weight: 600 });
    el.__ref = ref;
    dimFromStep(el, el.__main, 1, 0.45);
  },
  animate(el, d, s, A) {
    fadeIn(el.__ref, A, 200, 600);
    fadeIn(el.__main, A, 400, 900);
  },
};

/* ---------- Act 3: a Walker constellation ---------- */
// Orthographic view of the Walker shell (GCRF). Each plane is the exact circle through its satellites
// at the start epoch; the planes draw on one by one, then every satellite moves along its own plane
// at the orbital rate of the shell, one period per WALKER_LOOP_MS of wall time.
const WALKER_LOOP_MS = 20000;

figures.walkerGlobe = {
  needs: ['walker_pnt'],
  render(el, d) {
    const Wd = d.walker_pnt, S = Wd.snapshot_xyz_km, svg = svgFor(el), W = el.offsetWidth, H = el.offsetHeight;
    const r = Math.hypot(...S[0]), cx = W / 2, cy = H / 2, kmPerPx = r / (Math.min(W, H) / 2 - 12), re = R_EARTH / kmPerPx;
    const proj = projector(cx, cy, kmPerPx, 25, 28);
    const nP = Math.max(...Wd.planes) + 1;
    const normals = Array.from({ length: nP }, (_, p) => { const [a, b] = S.filter((_, i) => Wd.planes[i] === p); return unit3(cross3(a, b)); });
    const back = svgEl('g', {}, svg);
    el.__earth = svgEl('g', {}, svg);
    earth(el.__earth, cx, cy, re, 6701);
    const front = svgEl('g', {}, svg);
    el.__planes = normals.map((nv, p) => {
      const e1 = unit3(S[Wd.planes.indexOf(p)]), e2 = cross3(nv, e1);
      const pts = Array.from({ length: 181 }, (_, i) => { const a = i / 180 * 2 * Math.PI; return e1.map((v, c) => r * (v * Math.cos(a) + e2[c] * Math.sin(a))); });
      return frontBack(pts.map(proj), cx, cy, re).filter(q => q.pts.length > 1)
        .map(q => exactPath(q.h ? back : front, q.pts, { color: C.lagunita, width: 1.6, opacity: q.h ? 0.09 : 0.45 }));
    });
    const dots = svgEl('g', {}, svg);
    el.__planeDots = Array.from({ length: nP }, () => svgEl('g', {}, dots));
    el.__dots = S.map((_, i) => svgEl('circle', { r: 5, fill: C.lagunita }, el.__planeDots[Wd.planes[i]]));
    const omega = 2 * Math.PI / (Wd.span_h * 3600);
    el.__set = tSim => S.forEach((p, i) => {
      const nv = normals[Wd.planes[i]], q = cross3(nv, p), c = Math.cos(omega * tSim), s = Math.sin(omega * tSim);
      const pp = proj(p.map((v, k) => v * c + q[k] * s)), dot = el.__dots[i];
      dot.setAttribute('cx', pp[0].toFixed(1));
      dot.setAttribute('cy', pp[1].toFixed(1));
      dot.setAttribute('opacity', hidden(pp, cx, cy, re) ? 0.15 : 1);
    });
    el.__period = Wd.span_h * 3600;
    el.__set(0);
  },
  animate(el, d, s, A) {
    el.__set(0);
    fadeIn(el.__earth, A, 0, 600);
    el.__planes.forEach((paths, p) => {
      drawOnAnim(paths, A, 250 + p * 150, 700, 0);
      fadeIn(el.__planeDots[p], A, 550 + p * 150, 400);
    });
    const begin = 600 + el.__planes.length * 150;
    return loop(t => { if (t > begin) el.__set((t - begin) / WALKER_LOOP_MS * el.__period); });
  },
};

// Mean satellites in view above the elevation mask against latitude: GPS first, the Walker shell on
// click 1 (GPS dims), with the shell inclination marked.
figures.inViewByLat = {
  needs: ['walker_pnt'],
  render(el, d) {
    const V = d.walker_pnt.in_view, inc = d.walker_pnt.config.inc_deg, svg = svgFor(el);
    const hi = Math.ceil(Math.max(...V.walker_mean, ...V.gps_mean) / 2) * 2 + 1;
    const xr = [V.lat_deg[0], last(V.lat_deg)];
    const ax = axes(svg, { left: 100, right: 40, top: 30, bottom: 80, xr, yr: [0, hi], xlabel: 'latitude (degrees)', ylabel: `mean satellites above ${fmt(V.el_mask_deg, 0)}° elevation`, xticks: V.lat_deg, yticks: niceTicks(0, hi, 5), xfmt: v => `${v}°`, seed: 6801 });
    const series = (vals, color, width, g) => {
      const pts = vals.map((v, i) => [ax.x(V.lat_deg[i]), ax.y(v)]);
      const path = exactPath(g, pts, { color, width });
      pts.forEach(([x, y]) => svgEl('circle', { cx: x, cy: y, r: 6, fill: color }, g));
      return path;
    };
    el.__gps = svgEl('g', {}, svg);
    el.__gpsPath = series(V.gps_mean, C.ink, 3, el.__gps);
    haloText(el.__gps, ax.x(last(V.lat_deg)) - 4, ax.y(last(V.gps_mean)) - 18, 'GPS', { size: 26, anchor: 'end', weight: 600 });
    el.__walker = svgEl('g', { 'data-step': 1 }, svg);
    const ix = ax.x(inc);
    svgEl('line', { x1: ix, x2: ix, y1: ax.box.y0, y2: ax.box.y1, stroke: 'rgba(0,108,184,.45)', 'stroke-width': 2, 'stroke-dasharray': '6 7' }, el.__walker);
    haloText(el.__walker, ix + 10, ax.box.y1 + 20, `shell inclination, ${fmt(inc, 0)}°`, { size: 22, color: C.lagunita });
    el.__walkerPath = series(V.walker_mean, C.lagunita, 4.5, el.__walker);
    const pk = V.walker_mean.indexOf(Math.max(...V.walker_mean));
    haloText(el.__walker, ax.x(V.lat_deg[pk]) - 14, ax.y(V.walker_mean[pk]) - 18, `Walker shell, ${d.walker_pnt.config.t} satellites`, { size: 26, anchor: 'end', color: C.lagunita, weight: 600 });
    el.__axes = ax.g;
    dimFromStep(el, el.__gps, 1, 0.45);
  },
  animate(el, d, s, A) {
    fadeIn(el.__axes, A, 0, 500);
    drawOnAnim([el.__gpsPath], A, 200, 1200);
    return onStep(el, 1, () => drawOnAnim([el.__walkerPath], A, 100, 1300));
  },
};

/* ---------- Act 4: serial and parallel spherical-harmonic gravity ---------- */
// Log ticks at 1, 2 and 5 per decade inside [a, b], plus b itself, dropping ticks too close to b.
function logTicks([a, b]) {
  const out = [];
  for (let e = Math.floor(Math.log10(a)); e <= Math.ceil(Math.log10(b)); e++) [1, 2, 5].forEach(m => { const v = m * 10 ** e; if (v >= a - 1e-9 && v <= b + 1e-9) out.push(v); });
  return [...out.filter(v => Math.log10(b / v) > 0.12), b];
}

// Time per gravity evaluation against degree and order, log-log. Serial (ink) on entry with its
// interquartile band; parallel (Lagunita) on click 1; on click 2 brahe's automatic threshold as an
// exact vertical ink line and the measured crossover range as a shaded band.
figures.gravityCrossover = {
  needs: ['gravity_crossover'],
  render(el, d) {
    const G = d.gravity_crossover, n = G.degrees, svg = svgFor(el);
    const all = [...G.serial_us, ...G.parallel_us, ...G.serial_us_q25, ...G.serial_us_q75, ...G.parallel_us_q25, ...G.parallel_us_q75].filter(v => v > 0);
    const yr = [10 ** Math.floor(Math.log10(Math.min(...all))), 10 ** Math.ceil(Math.log10(Math.max(...all)))];
    const xr = [n[0], last(n)];
    const ax = axes(svg, { left: 100, right: 150, top: 60, bottom: 80, xr, yr, xlog: true, ylog: true, xlabel: 'spherical-harmonic degree and order (log scale)', ylabel: 'time per gravity evaluation (µs, log scale)', xticks: logTicks(xr), yfmt: v => (v < 1 ? fmt(v, 1) : fmtInt(v)), seed: 7101 });
    el.__axes = ax.g;
    const pts = vals => n.map((x, i) => [ax.x(x), ax.y(vals[i])]);
    const band = (lo, hi, color, op, g) => svgEl('path', { d: `${linPath([...pts(lo), ...pts(hi).reverse()])}Z`, fill: color, opacity: op, stroke: 'none' }, g);
    const ly = spreadLabels([ax.y(last(G.serial_us)), ax.y(last(G.parallel_us))].map(y => y + 8), 32);

    const B = ax.box;
    el.__mark = svgEl('g', { 'data-step': 2 }, svg);
    const R = G.crossover_range_nmax;
    const tx = ax.x(G.auto_threshold_nmax);
    if (R) {
      const [xa, xb] = [ax.x(R[0]), ax.x(R[1])];
      svgEl('rect', { x: xa, y: B.y1, width: Math.max(2, xb - xa), height: B.y0 - B.y1, fill: C.ink, opacity: 0.09 }, el.__mark);
      haloText(el.__mark, Math.min(xa, tx) - 12, B.y0 - 16, `measured crossover: degree ${R[0]} to ${R[1]}`, { size: 24, anchor: 'end', color: C.ink });
    }
    exactPath(el.__mark, [[tx, B.y0], [tx, B.y1 - 20]], { color: C.ink, width: 3 });
    haloText(el.__mark, tx - 10, B.y1 - 2, `brahe switches to parallel at degree ${G.auto_threshold_nmax}`, { size: 24, anchor: 'end', color: C.ink, weight: 600 });

    el.__serial = svgEl('g', {}, svg);
    band(G.serial_us_q25, G.serial_us_q75, C.ink, 0.14, el.__serial);
    el.__serialPath = exactPath(el.__serial, pts(G.serial_us), { color: C.ink, width: 3.5 });
    text(el.__serial, B.x1 + 16, ly[0], 'serial', { size: 26, color: C.ink, weight: 600 });

    el.__par = svgEl('g', { 'data-step': 1 }, svg);
    band(G.parallel_us_q25, G.parallel_us_q75, C.sky, 0.22, el.__par);
    el.__parPath = exactPath(el.__par, pts(G.parallel_us), { color: C.lagunita, width: 4.5 });
    text(el.__par, B.x1 + 16, ly[1], 'parallel', { size: 26, color: C.lagunita, weight: 600 });
  },
  animate(el, d, s, A) {
    fadeIn(el.__axes, A, 0, 500);
    drawOnAnim([el.__serialPath], A, 200, 1300);
    return onStep(el, 1, () => drawOnAnim([el.__parPath], A, 100, 1300));
  },
};

/* ---------- Act 4: benchmarks against other open-source libraries ---------- */
// One panel per task: a bar per library from the brahe (Rust) 1x line to its median-time ratio on a
// shared log axis (left of the line is faster than brahe, right is slower), brahe Python in
// Lagunita, the other libraries in ink, in the order of the results file. The last row holds the key.
figures.benchmarkRatios = {
  needs: ['benchmarks'],
  render(el, d) {
    const B = d.benchmarks, svg = svgFor(el), W = el.offsetWidth;
    const cols = 3, gapX = 56, gapY = 24, pw = (W - gapX * (cols - 1)) / cols;
    const rows = B.tasks.map(t => t.results.filter(r => !isBraheRust(r)));
    const pitch = 28, barH = 18, titleH = 38, axisH = 34, nameW = 132, valW = 66;
    const ph = titleH + Math.max(...rows.map(r => r.length)) * pitch + axisH;
    const ratios = B.tasks.flatMap(t => t.results.map(r => r.ratio_to_brahe));
    const lo = 10 ** Math.floor(Math.log10(Math.min(...ratios))), hi = 10 ** Math.ceil(Math.log10(Math.max(...ratios)));
    const X = scaleLog(lo, hi, nameW, pw - valW), x1 = X(1);
    el.__panels = B.tasks.map((t, k) => {
      const g = svgEl('g', { transform: `translate(${(k % cols) * (pw + gapX)} ${Math.floor(k / cols) * (ph + gapY)})` }, svg);
      text(g, 0, 26, t.label, { size: 24, weight: 600 });
      const yAxis = titleH + rows[k].length * pitch + 6;
      strokePath(g, roughLine(nameW - 4, yAxis, pw - valW + 6, yAxis, { seed: 7200 + k, rough: 0.6, passes: 1 }), { color: 'rgba(46,45,41,.5)', width: 2 });
      decades([lo, hi]).forEach(v => {
        svgEl('line', { x1: X(v), x2: X(v), y1: yAxis, y2: yAxis + 7, stroke: 'rgba(46,45,41,.45)', 'stroke-width': 2 }, g);
        text(g, X(v), yAxis + 30, v < 1 ? fmt(v, 1) : fmtInt(v), { size: 22, anchor: 'middle', color: 'rgba(46,45,41,.6)' });
      });
      rows[k].forEach((r, i) => {
        const y = titleH + i * pitch, v = r.ratio_to_brahe, xv = X(v), py = r.library === 'brahe';
        text(g, nameW - 12, y + barH - 1, libName(r), { size: 22, anchor: 'end', color: py ? C.lagunita : C.ink, weight: py ? 600 : 400 });
        svgEl('rect', { x: Math.min(x1, xv), y: y + 2, width: Math.max(2, Math.abs(xv - x1)), height: barH, fill: py ? C.lagunita : C.ink, opacity: py ? 0.85 : 0.7 }, g);
        text(g, v < 1 ? xv - 8 : xv + 8, y + barH - 1, `${ratioFmt(v)}×`, { size: 22, anchor: v < 1 ? 'end' : 'start', color: py ? C.lagunita : C.ink });
      });
      exactPath(g, [[x1, titleH - 6], [x1, yAxis]], { color: C.lagunita, width: 3 });
      return g;
    });
    // Key in the cells after the last panel.
    const k = B.tasks.length, kx = (k % cols) * (pw + gapX), ky = Math.floor(k / cols) * (ph + gapY);
    el.__key = svgEl('g', { transform: `translate(${kx} ${ky})` }, svg);
    exactPath(el.__key, [[8, 6], [8, 34]], { color: C.lagunita, width: 3 });
    text(el.__key, 30, 28, 'brahe (Rust), the 1× line', { size: 24, color: C.lagunita, weight: 600 });
    svgEl('rect', { x: 0, y: 50, width: 18, height: barH, fill: C.lagunita, opacity: 0.85 }, el.__key);
    text(el.__key, 30, 50 + barH - 1, 'brahe (Python)', { size: 24, color: C.lagunita, weight: 600 });
    svgEl('rect', { x: 0, y: 86, width: 18, height: barH, fill: C.ink, opacity: 0.7 }, el.__key);
    text(el.__key, 30, 86 + barH - 1, 'other open-source libraries', { size: 24, color: C.ink });
    el.insertAdjacentHTML('beforeend', `<p class="caption bench-key" style="position:absolute; left:${kx + 420}px; top:${ky - 6}px; width:${W - kx - 420}px; margin:0; text-wrap:balance;">Median time of each library divided by the median time of brahe (Rust) on the same task, log scale. Bars left of the line are faster than brahe, bars to the right are slower.</p>`);
  },
  animate(el, d, s, A) {
    el.__panels.forEach((g, i) => fadeIn(g, A, 150 + i * 120, 600));
    fadeIn(el.__key, A, 150 + el.__panels.length * 120, 600);
    fadeIn(el.querySelector('.bench-key'), A, 150 + el.__panels.length * 120, 600);
  },
};

/* ---------- backup: PDOP by latitude ---------- */
// Median PDOP against latitude, log scale: GPS first, the Walker shell on click 1 (GPS dims). A null
// median (no sample with enough satellites in view) leaves a gap in the line and is labeled.
figures.pdopByLat = {
  needs: ['walker_pnt'],
  render(el, d) {
    const D = d.walker_pnt.dop, svg = svgFor(el);
    const vals = [...D.walker_pdop_median, ...D.gps_pdop_median].filter(v => v != null);
    const yr = [10 ** Math.floor(Math.log10(Math.min(...vals))), 10 ** Math.ceil(Math.log10(Math.max(...vals)))];
    const xr = [D.lat_deg[0], last(D.lat_deg)];
    const ax = axes(svg, { left: 100, right: 40, top: 30, bottom: 80, xr, yr, ylog: true, xlabel: 'latitude (degrees)', ylabel: 'median PDOP (log scale)', xticks: D.lat_deg, xfmt: v => `${v}°`, yfmt: v => fmtInt(v), seed: 7301 });
    el.__axes = ax.g;
    const series = (v, color, width, g) => {
      const runs = [[]];
      v.forEach((y, i) => { if (y == null) runs.push([]); else last(runs).push([ax.x(D.lat_deg[i]), ax.y(y)]); });
      const paths = runs.filter(r => r.length > 1).map(r => exactPath(g, r, { color, width }));
      runs.flat().forEach(([x, y]) => svgEl('circle', { cx: x, cy: y, r: 6, fill: color }, g));
      return paths;
    };
    el.__gps = svgEl('g', {}, svg);
    el.__gpsPaths = series(D.gps_pdop_median, C.ink, 3, el.__gps);
    haloText(el.__gps, ax.x(D.lat_deg[0]) + 4, ax.y(D.gps_pdop_median[0]) + 36, 'GPS', { size: 26, weight: 600 });
    el.__walker = svgEl('g', { 'data-step': 1 }, svg);
    el.__walkerPaths = series(D.walker_pdop_median, C.lagunita, 4.5, el.__walker);
    haloText(el.__walker, ax.x(D.lat_deg[0]) + 4, ax.y(D.walker_pdop_median[0]) - 18, 'Walker shell', { size: 26, color: C.lagunita, weight: 600 });
    D.walker_pdop_median.forEach((v, i) => {
      if (v != null) return;
      const x = ax.x(D.lat_deg[i]);
      svgEl('line', { x1: x, x2: x, y1: ax.box.y0, y2: ax.box.y1, stroke: 'rgba(0,108,184,.45)', 'stroke-width': 2, 'stroke-dasharray': '6 7' }, el.__walker);
      haloText(el.__walker, x - 10, ax.box.y1 + 24, `no sample with ${MIN_SATS} in view`, { size: 22, anchor: 'end', color: C.lagunita });
    });
    dimFromStep(el, el.__gps, 1, 0.45);
  },
  animate(el, d, s, A) {
    fadeIn(el.__axes, A, 0, 500);
    drawOnAnim(el.__gpsPaths, A, 200, 1200);
    return onStep(el, 1, () => drawOnAnim(el.__walkerPaths, A, 100, 1300));
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
// One logo per organization from img/logos/, in a centered 3 x 3 grid.
figures.adopters = {
  render(el) {
    const logos = [['Northwood', 'northwood.svg'], ['Capella', 'capella.svg'], ['D-Orbit USA', 'd-orbit-usa.svg'], ['KSAT', 'ksat.svg'], ['HEO', 'heo.png'], ['Trusted Space', 'trusted-space.png'], ['K2 Space', 'k2-space.svg'], ['Vyoma', 'vyoma.svg'], ['Orbital Sidekick', 'orbital-sidekick.svg']];
    const cols = 3, pitch = 500, cw = 440, x0 = (el.offsetWidth - ((cols - 1) * pitch + cw)) / 2;
    el.innerHTML = logos.map(([n, file], i) => `<div class="logo-cell" data-rough="box" data-color="dim" data-rough-key="ad${i}" style="position:absolute; left:${x0 + (i % cols) * pitch}px; top:${Math.floor(i / cols) * 190}px; width:${cw}px; height:150px; display:flex; align-items:center; justify-content:center; padding:24px 16px;"><img src="img/logos/${file}" alt="${n}" style="width:100%; height:100%; object-fit:contain;"></div>`).join('');
  },
  animate(el, d, s, A) { [...el.children].forEach((c, i) => A.push(c.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 500, delay: 200 + i * 90, easing: EASE_IN, ...FILL }))); },
};

/* ---------- links: brahe and the talk's scripts ---------- */
figures.closeLinks = {
  render(el) {
    const block = (img, alt, label, urls) => `<div style="display:flex; flex-direction:column; align-items:center; width:720px; text-align:center;"><img src="${img}" alt="${alt}" style="width:300px; height:300px;"><div class="sans" style="margin-top:22px; font-size:30px; color:var(--ink-50); line-height:1.4">${label}${urls.map(u => `<br><b style="color:var(--lagunita); font-size:38px;">${u}</b>`).join('')}</div></div>`;
    el.innerHTML = `<div style="position:absolute; inset:0; display:flex; align-items:flex-start; justify-content:center; gap:80px;">${
      block('img/brahe-qr.webp', 'QR code for brahe.space', 'brahe documentation and source', ['brahe.space', 'github.com/duncaneddy/brahe'])}${
      block('img/repo-qr.webp', 'QR code for the talk repository', 'Scripts and slides for this talk', ['github.com/duncaneddy/2026_spnt_symposium'])}</div>`;
  },
  animate(el, d, s, A) { fadeIn(el.firstElementChild, A); },
};

/* ======================= slide-level animations ======================= */

export const slideAnims = {};
