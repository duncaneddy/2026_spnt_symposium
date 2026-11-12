# Practical Astrodynamics: SPNT Symposium (2026-11-12)

Documentation of the deck: story, visual system, conventions, data contracts and slide registry.

## Story

- **Audience:** GNSS and navigation researchers and practitioners. Strong on measurement models, estimation,
  signals and receivers. Less likely to have built orbit propagation, time systems or frame transformations.
- **Length:** 30 minute slot, main path planned for about 20 minutes, everything else after the Backup divider.
- **Audience belief to address:** satellite positions come from a file, and orbit modeling is someone
  else's problem that needs expensive or awkward tools.
- **Leave with:** real orbit analysis takes about ten lines of open-source code, and the hard parts (time,
  frames, fast dynamics) are already done correctly.
- **Framing line:** "brahe aims to be the numpy for space."
- **Outcomes:** an attendee can (1) download the orbit of a public satellite and propagate it, (2) simulate
  ranges and measurements from GPS satellites to a ground station or point, (3) simulate measurements from
  GPS satellites to another satellite.
- **Tone:** interactive. Questions to the room with a pause before the reveal, some light humor.
- **Running GNSS example:** ground station, then LEO receiver, then a receiver above the GPS constellation
  (MMS), then a designed constellation.

## Visual system

Follows the AA 279B `design-guidelines.md`.

| Role | Value | Meaning |
|---|---|---|
| Board (bg) | `#FAF8F3` | whiteboard |
| Ink | `#2E2D29` (Stanford Black) | default text, context |
| Cardinal | `#8C1515` | errors, the key word |
| Lagunita | `#006CB8` | orbits, brahe results |
| Sky | `#0098DB` | lighter orbit fills (at 15-25% opacity) |
| Palo Verde | `#279989` | the correct or resolved result |
| Gray | `#9A9A9A` / ink at 35-50% | context, dimmed prior beats |

- Type: **Source Serif 4** for statements (italic is the emphasis voice), **Source Sans 3** for labels, axes
  and data, **Source Code Pro** for code. Never below 22 px at 1920x1080.
- Hand-drawn: rough.js-style strokes for boxes, arrows, underlines and callouts (seeded so they render
  identically every time). Orbits, sky tracks, curves and anything measured are exact SVG paths.
- Footer: Stanford seal and name logo left, "2026 SPNT Symposium · Practical Astrodynamics" right.
- Motion: Web Animations API per the narrative-slides skill. Figures are precomputed and replayed; scripts
  write `deck/data/*.json` and the deck only interpolates.
- Copy: plain descriptive titles, no tagline-style lines, no em-dashes, no exclamation marks. Every number on
  a slide comes from `deck/data/*.json` via `data-bind`.

## Layout

```
scripts/      standalone `uv run` brahe scripts, each writes deck/data/<name>.json
deck/         index.html, js/, css/, fonts/, vendor/, data/, img/
justfile      `just data` regenerates the data except benchmarks.json (`just benchmarks`),
              `just serve` serves the deck on 8280, `just snippets` runs the code cards
pocs/         gitignored scratch
```

## Beat sheet

`[Q]` = pause and ask the room before revealing. `[S:name]` = data from `scripts/name.py`.

### Act 1: The problem (about 4 min)
1. Title.
2. Cold open. [Q] "Which GPS satellites are above this building right now?" Three levels of answering it (basic,
   TLE, full), each naming the same satellites with a different position error [S:three_levels]; then the sky
   plot over Stanford at the talk hour from an IGS SP3 file, with the code that made it. [S:skyplot]
3. Navigation is largely removing error: measurement error and dynamics model error. Dynamics are modelable
   but hard to get right and fast.
4. Existing tools trade off four properties: capable, fast, easy to use, open. [Q] "Which tool do you use, and
   which of these did you give up?"
5. The Poliastro quote.
6. brahe: aims to be the numpy for space. Since 2014, MIT, Rust core with Python bindings.

### Act 2: What is in it (about 4 min)
7. Module map: hand-drawn cards (time, frames and coordinates, orbits, propagation, access, data clients,
   estimation). Shown again in full ink as a recap before the adopters.
8. Design choices: SI units, composable pieces, compiled core, every documentation example run on each commit.
9. Quick hits, code and result side by side: CelesTrak ground tracks, force-model propagation, frame
   transforms. [S:quick_hits]

### Act 3: Use it (about 7 min)
10. Data clients. IGS SP3 download. [Q] "How far is the public TLE from the precise orbit for the same GPS
    satellite?" [S:tle_vs_sp3]
11. Time and frames. Station to GPS range, then GPS time read as UTC. [Q] "How big is the error?" [S:station_range]
    (In the backup, before the pseudorange slide.)
12. Composable. Receiver moves to LEO: one line changes. [S:leo_receiver]
13. MMS. [Q] "Can you use GPS from above the GPS constellation?" Transmit antenna pattern, Earth blockage,
    off-boresight angle computed from brahe states (geometric visibility, no link budget). [S:mms_visibility]
14. Design your own. Walker constellation, parallel numerical propagation, wall-clock time, satellites in view
    against GPS. [S:walker_pnt]

### Act 4: Making the hard part fast (about 3 min)
15. Spherical harmonic gravity cost and the parallel crossover. [S:gravity_crossover]
16. Benchmarks against Orekit, Nyx, Basilisk, OSTk and GMAT (June 2026 comparative run, brahe 1.6.1 development build). [S:benchmarks]

### Close (about 2 min)
17. Module map recap, then adoption by industry (logos).
18. On the horizon: GNSS orbit determination (RINEX), process noise models. How to get involved: share orbital
    observation sources, request features, contribute.
19. Links: brahe and this talk's repository.

### Backup
GPS time read as UTC (range mistake); pseudorange built term by term; dilution of precision for the designed constellation against GPS; event
detection; extensible dynamics; custom property computer detail; project history and test suite.

### Cut order if the main path runs long
MMS detail shortens to one slide, then beat 16 detail.

## Data contracts (scripts -> deck/data/*.json)

All scripts: PEP 723 header with `requires-python = ">=3.12"` and dependencies
brahe pinned to a commit on brahe's main branch that includes the IGS/SP3 client (to be replaced by a
released version when one is published) plus `numpy`, runnable as
`uv run scripts/<name>.py [--out path]`, default output `deck/data/<name>.json` resolved from the script
location, `generated_utc` in every file, each file under 2 MB. Units in key names (`_km`, `_m`, `_s`, `_h`,
`_deg`). ECI means GCRF unless the key says otherwise. Talk epoch 2026-11-12 19:00:00 UTC. Ground station:
Stanford campus, 37.4275 N, 122.1697 W, 30 m.

| File | Schema |
|---|---|
| `skyplot.json` | `{generated_utc, epoch_utc, product, station:{name, lat_deg, lon_deg, alt_m}, el_mask_deg, sats:[{prn, az_deg, el_deg, visible, track_azel_deg:[[az, el]]}], n_visible}` |
| `three_levels.json` | `{generated_utc, epoch_utc, station:{name, lon_deg, lat_deg, alt_m}, el_mask_deg, product, gp_source, gp_epoch_range_utc, n_sats, levels:[{key:"basic"\|"tle", n_visible, visible_prns, sky_err_deg:{median, max}, el_err_deg:{median, max_abs}, pos_err_km:{median, max}, n_mask_flips, flipped_prns}, {key:"precise", n_visible, visible_prns}], sats:[{prn, az_el_deg:{basic, tle, precise}}]}` |
| `quick_hits.json` | `{generated_utc, tle:{group, source, n, match_max_residual_km, inc_range_deg, epoch_utc, tracks:[{name, norad, inc_deg, lonlat_deg}]}, propagate:{object, inc_deg, t_h, alt_twobody_km, alt_full_km, dr_km, dr_drag_km, force_model}, frames:{prn, product, start_utc, t_h, eci_xyz_km, ecef_xyz_km}}` |
| `gps_constellation.json` | `{generated_utc, epoch_utc, talk_epoch_utc, talk_index, product, frame, step_s, period_s, prns, xyz_km:[time][satellite][x, y, z], planes}` |
| `land.json` | `{source, rings:[[[lon, lat]]]}` (Natural Earth 1:110m land, `scripts/basemap.py`) |
| `tle_vs_sp3.json` | `{generated_utc, prn, norad, object_name, gp_source, tle_epoch_utc, product, span_h, t_h, diff_rtn_km:{R, T, N}, diff_norm_km, rms_km, max_km}` |
| `station_range.json` | `{generated_utc, product, prn, station, gps_minus_utc_s, t_h, range_km, range_wrong_km, range_err_km, pos_err_km, max_range_err_km, terms_m:{geometric, light_time, earth_rotation, sat_clock}}` |
| `leo_receiver.json` | `{generated_utc, epoch_utc, product, gp_source, gp_epoch_utc, el_mask_deg, receiver:{name, norad, alt_km}, ground_station, t_min, n_visible_leo, n_visible_ground, mean_leo, mean_ground, orbit_xyz_km, links_at_epoch:{rx_xyz_km, gps_xyz_km, visible}}` |
| `mms_visibility.json` | `{generated_utc, gp_source, gps_source, span_utc, gps_products, object:{name, norad, gp_epoch_utc, perigee_alt_km, apogee_re}, gps_radius_km, pattern:{main_half_angle_deg, side_lobe_max_deg, earth_mask_alt_km, model, source}, receiver_note, t_h, radius_re, n_main, n_side, orbit_xyz_km, apogee_t_h, gps_xyz_at_apogee_km, gps_lobe_at_apogee, frac_time_4plus_main, frac_time_4plus_with_side}` |
| `walker_pnt.json` | `{generated_utc, config:{pattern, t, p, f, alt_km, inc_deg, source, force_model, integrator, mass_kg, drag_area_m2, cd, srp_area_m2, cr}, span_h, threads, wall_s_serial, wall_s_parallel, speedup, snapshot_xyz_km, planes, one_orbit_xyz_km, in_view:{lat_deg, walker_mean, gps_mean, el_mask_deg}, dop:{lat_deg, walker_pdop_median, gps_pdop_median, skipped:{walker, gps}, samples_per_lat}}` (a null median PDOP means no sample had 4 satellites in view) |
| `gravity_crossover.json` | `{generated_utc, machine:{cpu, threads, load_avg_1min_start, load_avg_1min_end}, model, model_file_bytes, max_degree_available, kernel, integrator, steps, passes, repeats_per_pass, stages_per_step, method, degrees, serial_us, parallel_us, serial_us_q25, serial_us_q75, parallel_us_q25, parallel_us_q75, overhead_us_degree2, auto_threshold_nmax, measured_crossover_nmax, crossover_range_nmax}` |
| `benchmarks.json` | `{generated_utc, brahe_version, brahe_build, benchmark_run_utc, statistic, iterations, source, hardware, library_versions, excluded:{<library>:{reason, version, min_median_s}}, tasks_in_run, tasks:[{name, label, batch, results:[{library, language, median_s, ratio_to_brahe}]}], faster_elsewhere:[{task, library, ratio_to_brahe}]}` |

## Slide registry

Numbers are the footer numbers (a continuation shares the number of the slide it builds on).

| # | Label | Figure / data | Transition |
|---|---|---|---|
| 1 | Title | `gpsConstellation` / gps_constellation.json | fresh; orbits draw on, satellites fade in and loop over one period from the talk-time sample (75 s per period) |
| 2 | Sky Q | none | fresh; question alone (`data-flip="q-sky"`) |
| 3 | Three levels | `threeLevels` / three_levels.json | magic move: question becomes the header; clicks 1 to 3: Basic, Better and Full cards, each with its count above the mask (and for Basic and Better the median position error, median sky-direction error beneath); click 4: closing sentence |
| 4 | Sky plot | `skyplot`, `code-skyplot` / skyplot.json | same header as Three levels (no move); plot draws on, code card rises, count caption fades |
| 5 | Errors | none | fresh; two boxes, each with its description; the measurement box adds that system design can reduce measurement error |
| 5 | Errors 2 | none | continuation of Errors: measurement box dimmed, dynamics title and description move (`dyn-title`, `dyn-desc`) into a larger box that draws on, forces rise; click 1: the takeaway sentence |
| 6 | Tradeoff | `tradeoff` | fresh; property cards rise; click 1: question; clicks 2 to 4: one tool family row each, symbols check (Palo Verde), tilde (sometimes, ink) and x (no, ink at 45%); click 2 also shows the legend and the tendencies caption |
| 7 | Quote | none | fresh; quote and attribution. Holds hidden copies of the property cards at their Tradeoff positions as magic-move sources for the next slide |
| 8 | brahe | `check` x4 / facts from `BRAHE` in figs.js | magic move: property cards fly from their Tradeoff positions into a row; checks draw; facts and install line fade |
| 9 | Modules | `moduleMap` | fresh; cards rise one by one |
| 10 | Design choices | none | fresh; first panel on entry, clicks 1 to 3: one panel each |
| 8 | Modules zoom | `moduleMap` (clone of Modules), `moduleZoomKeys` | continuation of Modules; `moduleZoomKeys` gives each cloned card title and icon a `data-flip` key (`mod-<key>`, `mod-<key>-icon`) |
| M1 | Module Time | `modIcon`, `code-modTime` (snippets/mod_time.py) | magic move: the Time card title and icon fly into the header while a hidden copy of the map and its header fade out (`data-dim-to="0"`); supports list fades, code card rises |
| M2 | Module Frames | `modIcon`, `code-modFrames` (snippets/mod_frames.py) | fresh; icon, header, supports list (four groups), code card |
| M3 | Module Orbits | `modIcon`, `code-modOrbits` (snippets/mod_orbits.py) | fresh; same layout |
| M4 | Module Propagation | `modIcon`, `code-modPropagation` (snippets/mod_propagation.py) | fresh; same layout |
| M5 | Module Access | `modIcon`, `code-modAccess` (snippets/mod_access.py) | fresh; same layout |
| M6 | Module Data | `modIcon`, `code-modData` (snippets/mod_data.py) | fresh; same layout |
| M7 | Module Estimation | `modIcon`, `code-modEstimation` (snippets/mod_estimation.py) | fresh; same layout, no label above the code card (the card fills the column) |
| 11 | Quick TLE | `code-tle`, `groundTracks` / quick_hits.json, land.json, skyplot.json | fresh; code card rises, tracks draw on |
| 12 | Quick force model | `code-propagate`, `forceModelEffect` / quick_hits.json | fresh; curves draw on, labels fade |
| 13 | Quick frames | `code-frames`, `eciVsEcef` / quick_hits.json | fresh; both frames draw on together |
| 14 | TLE vs IGS | `code-tleSp3`, `tleVsSp3` / tle_vs_sp3.json | fresh; question as header, code card rises; click 1: R, T, N curves draw on (along-track in Cardinal) with RMS and largest difference |
| 15 | LEO receiver | `code-leoReceiver`, `leoLinks` / leo_receiver.json | fresh; code card with the ISS argument in Cardinal; Earth, ISS orbit and lines of sight to visible GPS satellites draw on, to scale |
| 16 | LEO counts | `leoCounts` / leo_receiver.json | fresh; ground series with mean; click 1: ISS series with mean, ground dims, comparison caption |
| 17 | MMS orbit | `mmsOrbit` / mms_visibility.json | fresh; question as header, orbit face-on to scale with GPS radius circle, main and side lobe half angles for one GPS satellite, Earth shadow; click 1: replay of MMS along the orbit (50 s per orbit) with distance and counts in the readout (`data-readout`, refreshed twice a second), a trace of the main-lobe count over the orbit (`data-mms-trace`), "Geometric visibility, no link budget" |
| 18 | MMS counts | `mmsCounts` / mms_visibility.json | fresh; main-lobe counts against radius and its 4+ fraction; click 1: main or side lobes, main dims, second fraction and no-link-budget label |
| 19 | Walker build | `code-walker`, `walkerGlobe` / walker_pnt.json | fresh; planes draw on one by one, then satellites move (kinematic, one period per 20 s); click 1: serial, parallel, threads, speedup |
| 20 | Walker in view | `inViewByLat` / walker_pnt.json | fresh; GPS by latitude; click 1: Walker shell with inclination line, GPS dims, comparison sentence; cite is `config.source` |
| 21 | Gravity | `gravityCrossover` / gravity_crossover.json | fresh; log-log axes, serial line with interquartile band draws on, serial values at the low and highest degree; click 1: parallel line and band (Lagunita) draw on, parallel values; click 2: brahe's automatic threshold as an exact vertical line, measured crossover range as a shaded band, sentence on the automatic switch |
| 22 | Benchmarks | `benchmarkRatios` / benchmarks.json | fresh; one row per task on a shared log axis of time relative to brahe (Rust), brahe as the Lagunita 1x line, every other library an ink dot with its name (ratio added for dots on the faster side); rows fade in one by one; captions bind the Python overhead range and the count of tasks in the run where another library is faster |
| 23 | Modules recap | `moduleMap` | fresh; the module map again in full ink, cards rise one by one |
| 24 | Adopters | `adopters` | fresh; ten logos in a 5 x 2 grid, cells fade in |
| 25 | Next | none | fresh; roadmap panel; click 1: "How you can get involved" panel with share data; clicks 2 and 3: request features, contribute |
| 26 | Links | `closeLinks` | fresh; name and email under the header; two 440 px QR codes side by side, each with its label and URLs beneath: brahe (`img/brahe-qr.webp`, brahe.space and github.com/duncaneddy/brahe) and the talk repository (`img/repo-qr.webp`, github.com/duncaneddy/2026_spnt_symposium) |
| B | Backup | none | divider |
| B1 | Range mistake | `code-rangeEpochs`, `rangeMistake` / station_range.json | fresh; code card with `bh.GPS` (Palo Verde) and `bh.UTC` (Cardinal), question "How big is the error?"; click 1: satellite position error and GPS minus UTC; click 2: range error curve over the pass with its largest value |
| B2 | Pseudorange | none / station_range.json (`terms_m`) | fresh; equation and geometric range; clicks 1 to 3: light time, Earth rotation (the three rows that sum to rho), satellite clock |
| B3 | PDOP | `pdopByLat` / walker_pnt.json (`dop`) | fresh; GPS median PDOP by latitude (log); click 1: Walker shell with a gap and label where the median is null, GPS dims, skipped-sample counts |
| B4 | Events | `code-valueEvent` (snippets/value_event.py) | fresh; after brahe example custom_value_event.py |
| B5 | Extensible dynamics | `code-additionalDynamics` (snippets/battery.py) | fresh; after brahe example battery_tracking.py |
| B6 | Sensitivity | `code-sensitivity` (snippets/sensitivity.py) | fresh, same header as B5 without entry motion; after brahe example sensitivity_analysis.py |
| B7 | Property computer | `code-propertyComputer`, `code-propertyAccess` (one program, snippets/property_computer.py, split before `t0 = bh.Epoch(`) | fresh; after brahe example custom_property_computer.py, note that access takes ground locations |
| B8 | History | none | fresh; two panels: examples and tests in CI, tests and LLM-assisted maintenance |
| B9 | Benchmark detail | `benchmarkDetail` / benchmarks.json | fresh; table of every ratio on the Benchmarks slide, and every task in the run where another library is faster than brahe (Rust) |

## Deck implementation

- Shell: `deck/js/deck.js` (stage scaling, keys, hash routing, chrome, continuations, entry choreography, FLIP).
- Strokes: `deck/js/sketch.js` (seeded hand-drawn lines, boxes and ellipses; `[data-rough]` auto-decoration,
  seed from `data-rough-key` or text so clones redraw identically).
- Module slides and the benchmark figures: `deck/js/modules.js` and `deck/css/modules.css`, registered into
  `figures`, `binds` and `CODE` by a hook in figs.js after `CODE`.
- Figures: `deck/js/figs.js` (`figures.<name> = {needs, render(el, data, state), animate(el, data, state, A)}`,
  `binds` for `[data-bind]` numbers, `DATA_FILES` lists the JSON files loaded at startup).
- A figure with `needs: ['<file>']` shows "data pending: run scripts/<file>.py" when that JSON is missing.
- Declarative motion: `data-in="up|fade|pop|wipe|draw"` plus `data-delay`; magic move with matching
  `data-flip` keys on adjacent slides; continuation with `data-clone="<label>"`, `data-dim="<sel>:<opacity>"`,
  `data-figstate`, `data-drop`.
- Chrome: `data-stage` shows a section name at the top; `data-nofooter` hides the footer.
- Click steps: `data-step="n"` on HTML or SVG elements; figures listen with `onStep(el, n, fn)`.
- Math: `\( ... \)` in slide text is typeset by the bundled KaTeX.
- Keys: arrows or space, `n` notes, `b` backup, `r` replay, `f` full screen.
- Dev server: `just serve` (`scripts/serve.py`, no-cache headers) on port 8280.
- Code cards: every card shows a complete, runnable program from `deck/snippets/<name>.py`. The deck
  fetches the files at load (figs.js, top-level `await`, next to the data fetch) and shows each file
  below its PEP 723 header and the blank line after it, verbatim except for the lines named in the
  entry's `hide` list (alias constants such as `DEG = ...` whose full name would wrap, and the closing
  `print`); there is no second copy of the code.
  The files live under `deck/` because the dev server serves only that directory. A file that fails to
  load shows "snippet pending: deck/snippets/<name>.py" instead of the card.
- Snippet convention for a new card: one file per card, PEP 723 header (`requires-python = ">=3.12"`,
  the same brahe pin as `scripts/`, `numpy` only when used), then imports, every constant as a literal
  (station as `[lon, lat, alt]`, epoch as `bh.Epoch(...)`, product names as strings), the computation
  with the same brahe calls and physics as the matching analysis script, and one closing `print` of the
  number the slide shows (hidden on the card). IGS products are found with
  `list_products_between(epoch, epoch, center="IGS", solution="ULT", content="ORB")`, taking the last
  (latest) entry, rather than by file name. No helpers or names from elsewhere, no argparse, JSON or caching code, no
  asserts. Format with `uvx ruff format --line-length 68 deck/snippets` (never re-wrap by hand) and keep
  `uvx ruff check --select F821,F401,F841 deck/snippets` clean. Fit: at 22 px a card holds about 25
  lines below a one-line header (blank lines count half), and is 13.2 px per character plus 56 px of
  padding wide (68 characters: 954 px). Run every snippet with `just snippets`.
- `codeCard(el, lines, {highlight, steps, marks, size, key})` in figs.js draws monospace Python in a
  hand-drawn box as wide as `el`, with non-blank lines numbered 1..n in a gray gutter; brahe calls
  (`bh.*`) in Lagunita, keywords in Palo Verde, numbers in Sky, strings in dimmed ink, comments gray
  italic; Cardinal marks are bold and underlined; line height 1.25, blank lines at half height. With the
  gutter a 68-character line needs about 960 px at 22 px. Lines are selected by a substring match (the first line that contains it), never by editing
  the code text: `highlight: ['match']` draws that line in Cardinal; `highlight: [['match', k]]` turns
  it Cardinal on click k; `steps: {'match': k}` hides it until click k. `CODE` entries are
  `key: {file, from, to, hide, opts}`; `hide` lists line matches left off the card; `from`/`to` (line matches) split one program across two cards
  (property computer). Each entry is registered as figure `code-<key>`.
- Module map: `figures.moduleMap` renders one card per entry of `MODULES` (keys `time`, `frames`,
  `orbits`, `propagation`, `access`, `data`, `estimation`); the Modules slide and the Modules recap
  each place it directly. Divider slides (none in the deck at present):
  `<section class="slide" data-label="Section X" data-clone="Modules" data-lc-current="data">` (several
  keys comma separated, e.g. `"time,frames"`). Current cards turn Cardinal, cards current on an earlier
  divider turn gray, the rest stay ink; moving between adjacent dividers animates the colors.
- Magic moves of hand-drawn boxes: put the outline on an inner element and `data-flip` on a positioned
  wrapper (see `.prop-slot`), so the outline moves with the card.
- Code card token colors: `marks: [['line match', 'text', 'cardinal' | 'green']]` in a `CODE` entry's
  `opts` colors that text on the first line containing the match (one mark per line), e.g. `bh.UTC` on
  the `mistaken = bh.Epoch(` line and the ISS argument on the `n_iss = gps_in_view(` line.
- Figures revealed on a click: put `data-step="n"` on the `.fig` div and start draw-ons with
  `whenShown(el, fn)`, which runs fn now or on the click that reveals el. `dimFromStep(el, g, n, op)`
  dims a group from step n onward in both directions. Comparison charts (`leoCounts`, `mmsCounts`,
  `inViewByLat`) show the familiar series first and add the new one on click 1 with the first dimmed.
- Replays: `mmsOrbit` (replay starts on click 1, or on arrival when the slide is entered fully built)
  and `walkerGlobe` (kinematic: each satellite rotates along its own plane at the shell's orbital rate,
  one period per 20 s) return cancel functions. With reduced motion, `mmsOrbit` stays at the apogee
  sample and `walkerGlobe` at the start epoch. `mmsOrbit` writes its readout into the slide's
  `[data-readout="r|main|side"]` fields at most twice a second (the current sample's values, distance in
  whole Earth radii while moving) and draws the main-lobe trace into `[data-mms-trace]`.
