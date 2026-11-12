// Per-module slides (zoom from the module map into one card, its code card) and the benchmark
// comparison. Registered into figs.js's `figures`, `binds` and `CODE` by figs.js.
import { svgEl, strokePath, roughLine, roughArrow, hashSeed } from './sketch.js';
import { svgFor, text, haloText, exactPath, fadeIn, fmt, fmtInt, scaleLog, decades, moduleIcon, libName, listAnd, C } from './figs.js';

/* ---------- module slides ---------- */

// One snippet per module slide: figure `code-mod<Name>` shows deck/snippets/mod_<module>.py.
export const moduleCode = {
  modTime: { file: 'mod_time' },
  modFrames: { file: 'mod_frames' },
  modOrbits: { file: 'mod_orbits' },
  modPropagation: { file: 'mod_propagation' },
  modAccess: { file: 'mod_access' },
  modData: { file: 'mod_data' },
  modEstimation: { file: 'mod_estimation' },
};

/* ---------- benchmarks ---------- */

// Tasks whose brahe (Rust) median is at least this long count as heavy in the Python overhead line.
const HEAVY_S = 1e-4;
const B = d => d.benchmarks;
const rustOf = t => t.results.find(r => r.library === 'brahe' && r.language === 'rust');
const pyRatio = t => t.results.find(r => r.library === 'brahe' && r.language === 'python')?.ratio_to_brahe;
const heavy = d => B(d).tasks.filter(t => rustOf(t).median_s >= HEAVY_S);
const light = d => B(d).tasks.filter(t => rustOf(t).median_s < HEAVY_S);
const ratioFmt = v => (v < 0.1 ? fmt(v, 3) : v < 1 ? fmt(v, 2) : v < 10 ? fmt(v, 1) : fmtInt(v));
const range = (vals, d) => { const lo = Math.min(...vals), hi = Math.max(...vals); return `${fmt(lo, d)} to ${fmt(hi, d)}`; };
const COUNT_WORDS = ['no', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten'];
const countWord = n => COUNT_WORDS[n] ?? String(n);
const otherLibs = d => [...new Set(B(d).tasks.flatMap(t => t.results.filter(r => r.library !== 'brahe').map(r => r.library)))];
const libWithVersion = (d, lib) => { const v = B(d).library_versions?.[lib]; return v ? `${libName({ library: lib })} ${v}` : libName({ library: lib }); };
const fasterTasks = d => [...new Set(B(d).faster_elsewhere.map(f => f.task))];
const UTC_DATE = new Intl.DateTimeFormat('en-US', { timeZone: 'UTC', month: 'long', day: 'numeric', year: 'numeric' });

export const moduleBinds = {
  'benchmark.run': d => UTC_DATE.format(new Date(B(d).benchmark_run_utc)),
  'benchmark.brahe': d => `brahe ${B(d).brahe_version}${B(d).brahe_build ? ' development build' : ''}`,
  'benchmark.hardware': d => B(d).hardware,
  'benchmark.iterations': d => String(B(d).iterations),
  'benchmark.libs': d => listAnd(otherLibs(d).sort((a, b) => libName({ library: a }).localeCompare(libName({ library: b }))).map(lib => libWithVersion(d, lib))),
  'benchmark.excluded': d => Object.entries(B(d).excluded || {}).map(([lib, e]) => `${libName({ library: lib })}${e.version ? ` ${e.version}` : ''}`).join(', ') || undefined,
  'benchmark.excludedMin': d => { const m = Object.values(B(d).excluded || {}).map(e => e.min_median_s); return m.length ? fmt(Math.min(...m), 2) : undefined; },
  'benchmark.heavyUs': () => fmtInt(HEAVY_S * 1e6),
  'benchmark.nHeavy': d => countWord(heavy(d).length),
  'benchmark.nLight': d => countWord(light(d).length),
  'benchmark.pyHeavy': d => range(heavy(d).map(pyRatio), 1),
  'benchmark.pyLight': d => range(light(d).map(pyRatio), 0),
  'benchmark.nFaster': d => String(fasterTasks(d).length),
  'benchmark.nRun': d => String(B(d).tasks_in_run),
};

// One row per task on a shared log axis of time relative to brahe (Rust): brahe is the Lagunita 1x
// line, every other library an ink dot with its name, de-overlapped above and below the row. Dots
// left of the line (faster than brahe) carry their ratio as well. brahe's Python bindings are not
// plotted (the slide states their overhead in a caption line).
function benchmarkRender(el, d) {
  const T = B(d).tasks, svg = svgFor(el), W = el.offsetWidth, H = el.offsetHeight;
  const labelW = 500, top = 70, axisH = 78, right = 70;
  const pitch = (H - top - axisH) / T.length;
  const marks = T.map(t => t.results.filter(r => r.library !== 'brahe'));
  const all = marks.flat().map(r => r.ratio_to_brahe);
  const lo = Math.min(0.1, 10 ** Math.floor(Math.log10(Math.min(...all)))), hi = 10 ** Math.ceil(Math.log10(Math.max(...all)));
  const X = scaleLog(lo, hi, labelW + 20, W - right), x1 = X(1), yAxis = H - axisH + 14;

  el.__frame = svgEl('g', {}, svg);
  strokePath(el.__frame, roughLine(labelW + 10, yAxis, W - right + 16, yAxis, { seed: 7400, rough: 0.8 }), { color: 'rgba(46,45,41,.55)', width: 2.2 });
  decades([lo, hi]).forEach(v => {
    svgEl('line', { x1: X(v), x2: X(v), y1: yAxis, y2: yAxis + 8, stroke: 'rgba(46,45,41,.45)', 'stroke-width': 2 }, el.__frame);
    text(el.__frame, X(v), yAxis + 34, `${v < 1 ? fmt(v, 1) : fmtInt(v)}×`, { size: 22, anchor: 'middle', color: 'rgba(46,45,41,.6)' });
  });
  text(el.__frame, (labelW + W) / 2, H - 4, 'median time relative to brahe (Rust), log scale', { size: 24, anchor: 'middle', color: 'rgba(46,45,41,.7)' });
  strokePath(el.__frame, roughArrow(x1 - 24, 26, x1 - 150, 26, { seed: 7401, head: 10, rough: 0.5 }), { color: 'rgba(46,45,41,.55)', width: 2.2 });
  text(el.__frame, x1 - 162, 34, 'faster than brahe', { size: 24, anchor: 'end', color: 'rgba(46,45,41,.7)' });
  strokePath(el.__frame, roughArrow(x1 + 24, 26, x1 + 150, 26, { seed: 7402, head: 10, rough: 0.5 }), { color: 'rgba(46,45,41,.55)', width: 2.2 });
  text(el.__frame, x1 + 162, 34, 'slower than brahe', { size: 24, color: 'rgba(46,45,41,.7)' });
  exactPath(el.__frame, [[x1, top - 8], [x1, yAxis]], { color: C.lagunita, width: 3 });
  haloText(el.__frame, x1, top - 18, 'brahe (Rust)', { size: 22, anchor: 'middle', color: C.lagunita, weight: 600 });

  const placed = [[x1 - 2, -Infinity, x1 + 2, Infinity]];
  const clear = b => placed.every(p => b[2] < p[0] - 8 || b[0] > p[2] + 8 || b[3] < p[1] || b[1] > p[3]);
  el.__rows = T.map((t, k) => {
    const g = svgEl('g', {}, svg), y = top + pitch * (k + 0.5);
    text(g, 0, y - 2, t.label, { size: 26, weight: 600 });
    text(g, 0, y + 26, t.batch ? `per call: ${t.batch}` : '', { size: 22, color: 'rgba(46,45,41,.55)' });
    svgEl('line', { x1: labelW + 20, x2: W - right, y1: y, y2: y, stroke: 'rgba(46,45,41,.12)', 'stroke-width': 1.5 }, g);
    [...marks[k]].sort((a, b) => a.ratio_to_brahe - b.ratio_to_brahe).forEach(r => {
      const v = r.ratio_to_brahe, x = X(v), faster = v < 1;
      svgEl('circle', { cx: x, cy: y, r: 8, fill: C.ink }, g);
      const lbl = faster ? `${libName(r)} ${ratioFmt(v)}×` : libName(r);
      const t0 = text(g, 0, 0, lbl, { size: 22, color: C.ink, weight: faster ? 600 : 400 });
      const w = t0.getComputedTextLength();
      const cands = faster
        ? [[x - 16 - w, y + 8], [x - w / 2, y - 16], [x - w / 2, y + 34]]
        : [[x - w / 2, y - 16], [x - w / 2, y + 34], [x + 4, y - 16], [x + 4, y + 34], [x - w - 4, y - 16], [x - w - 4, y + 34], [x + 16, y + 8]];
      const box = ([lx, ly]) => [lx, ly - 18, lx + w, ly + 4];
      const pick = cands.find(c => clear(box(c)) && c[0] >= labelW + 10) || cands[0];
      placed.push(box(pick));
      t0.setAttribute('x', pick[0]); t0.setAttribute('y', pick[1]);
    });
    return g;
  });
}

function benchmarkAnimate(el, d, s, A) {
  fadeIn(el.__frame, A, 0, 500);
  el.__rows.forEach((g, i) => fadeIn(g, A, 200 + i * 120, 500));
}

// Backup table: every selected task's ratios by library, and every task in the run where another
// library is faster than brahe (Rust).
function benchmarkDetailRender(el, d) {
  const T = B(d).tasks, libs = [['brahe', 'python'], ...otherLibs(d).map(l => [l, null])];
  const head = libs.map(([l, lang]) => `<span class="v">${lang ? 'brahe Python' : libName({ library: l })}</span>`).join('');
  const rows = T.map(t => `<div class="bd-row"><span>${t.label}</span>${libs.map(([l, lang]) => {
    const r = t.results.find(x => x.library === l && (!lang || x.language === lang));
    return `<span class="v${r && r.ratio_to_brahe < 1 ? ' faster' : ''}">${r ? `${ratioFmt(r.ratio_to_brahe)}×` : '–'}</span>`;
  }).join('')}</div>`).join('');
  const faster = B(d).faster_elsewhere.map(f => `<div class="bd-fast"><code>${f.task}</code><span>${libName(f)}</span><span class="v faster">${ratioFmt(f.ratio_to_brahe)}×</span></div>`).join('');
  el.innerHTML = `<div class="bd-table" style="--bd-cols:${libs.length}"><div class="bd-row head"><span>Task</span>${head}</div>${rows}</div>
    <div class="bd-list"><div class="bd-sub">Every task in the run where another library is faster than brahe (Rust)</div><div class="bd-items">${faster}</div></div>`;
}

export const moduleFigures = {
  // Placed on the map slide that starts the module sequence: gives each cloned card's title and
  // icon a data-flip key (mod-<key>, mod-<key>-icon) so the next slide's header can move from it.
  moduleZoomKeys: {
    render(el) {
      el.closest('section').querySelectorAll('.mod-card').forEach(card => {
        const k = card.dataset.lc, h = card.querySelector('h3');
        h.innerHTML = `<span class="mod-flip" data-flip="mod-${k}">${h.innerHTML}</span>`;
        card.querySelector('.icon').dataset.flip = `mod-${k}-icon`;
      });
    },
  },
  // A module card's icon on its own, at the card's icon size; data-state is the module key.
  modIcon: {
    render(el) { moduleIcon(svgFor(el), el.dataset.state, el.offsetWidth, hashSeed(el.dataset.state)); },
  },
  benchmarkRatios: { needs: ['benchmarks'], render: benchmarkRender, animate: benchmarkAnimate },
  benchmarkDetail: { needs: ['benchmarks'], render: benchmarkDetailRender },
};
