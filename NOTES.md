# Practical Astrodynamics: SPNT Symposium (2026-11-12)

Working notes for the deck. Not talk content.

## Story

- **Audience:** GNSS and navigation researchers and practitioners. Strong on measurement models, estimation,
  signals and receivers. Less likely to have built orbit propagation, time systems or frame transformations.
- **Length:** 30 minute slot, main path planned for about 20 minutes, everything else after the Backup divider.
- **Naive belief (builder's guess):** satellite positions come from a file, and orbit modeling is someone
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
justfile      `just data` regenerates all data, `just serve` serves the deck on 8280
pocs/         gitignored scratch
```

## Beat sheet

`[Q]` = pause and ask the room before revealing. `[S:name]` = data from `scripts/name.py`.

### Act 1: The problem (about 4 min)
1. Title.
2. Cold open. [Q] "Which GPS satellites are above this building right now?" Sky plot over Stanford at the talk
   hour from an IGS SP3 file, with the ten lines of code that made it. [S:skyplot]
3. Navigation is largely removing error: measurement error and dynamics model error. Dynamics are modelable
   but hard to get right and fast.
4. Existing tools trade off four properties: capable, fast, easy to use, open. [Q] "Which tool do you use, and
   which of these did you give up?"
5. The Poliastro quote. Presenter line: "I enjoy both, a lot."
6. brahe: aims to be the numpy for space. Since 2014, MIT, Rust core with Python bindings.

### Act 2: What is in it (about 4 min)
7. Module map: hand-drawn cards (time, frames and coordinates, orbits, propagation, access, data clients,
   estimation). Reused as divider and lit up as later beats use each module.
8. Design choices: SI units, composable pieces, compiled core, every documentation example run on each commit.
9. Quick hits, code and result side by side: CelesTrak ground tracks, force-model propagation, frame
   transforms. [S:quick_hits]

### Act 3: Use it (about 7 min)
10. Data clients. IGS SP3 download. [Q] "How far is the public TLE from the precise orbit for the same GPS
    satellite?" [S:tle_vs_sp3]
11. Time and frames. Station to GPS range, then GPS time read as UTC. [Q] "How big is the error?" [S:station_range]
12. Composable. Receiver moves to LEO: one line changes. [S:leo_receiver]
13. MMS. [Q] "Can you use GPS from above the GPS constellation?" Transmit antenna pattern, Earth blockage,
    off-boresight angle computed from brahe states (geometric visibility, no link budget). [S:mms_visibility]
14. Design your own. Walker constellation, parallel numerical propagation, wall-clock time, satellites in view
    against GPS. [S:walker_pnt]

### Act 4: Making the hard part fast (about 3 min)
15. Spherical harmonic gravity cost and the parallel crossover. [S:gravity_crossover]
16. Benchmarks against Orekit, GMAT, Nyx, Basilisk (brahe 1.5.2 results). [S:benchmarks]

### Close (about 2 min)
17. Adoption by industry (logos).
18. On the horizon: GNSS orbit determination (RINEX), process noise models. The ask: shareable orbital
    observation sources.
19. Links: brahe and this talk's repository.

### Backup
Pseudorange built term by term; dilution of precision for the designed constellation against GPS; event
detection; extensible dynamics; custom property computer detail; benchmark detail; project history and test
suite; Humphreys paper reproduction if built.

### Cut order if the main path runs long
MMS detail shortens to one slide, then beat 16 detail, then beat 11's mistake reveal moves to backup.

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
| `quick_hits.json` | `{generated_utc, tle:{group, source, n, match_max_residual_km, inc_range_deg, epoch_utc, tracks:[{name, norad, inc_deg, lonlat_deg}]}, propagate:{object, inc_deg, t_h, alt_twobody_km, alt_full_km, dr_km, dr_drag_km, force_model}, frames:{prn, product, start_utc, t_h, eci_xyz_km, ecef_xyz_km}}` |
| `gps_constellation.json` | `{generated_utc, epoch_utc, talk_epoch_utc, talk_index, product, frame, step_s, period_s, prns, xyz_km:[time][satellite][x, y, z], planes}` |
| `land.json` | `{source, rings:[[[lon, lat]]]}` (Natural Earth 1:110m land, `scripts/basemap.py`) |
| `tle_vs_sp3.json` | `{generated_utc, prn, norad, object_name, gp_source, tle_epoch_utc, product, span_h, t_h, diff_rtn_km:{R, T, N}, diff_norm_km, rms_km, max_km}` |
| `station_range.json` | `{generated_utc, product, prn, station, gps_minus_utc_s, t_h, range_km, range_wrong_km, range_err_km, pos_err_km, max_range_err_km, terms_m:{geometric, light_time, earth_rotation, sat_clock}}` |
| `leo_receiver.json` | `{generated_utc, epoch_utc, product, gp_source, gp_epoch_utc, el_mask_deg, receiver:{name, norad, alt_km}, ground_station, t_min, n_visible_leo, n_visible_ground, mean_leo, mean_ground, orbit_xyz_km, links_at_epoch:{rx_xyz_km, gps_xyz_km, visible}}` |
| `mms_visibility.json` | `{generated_utc, gp_source, gps_source, span_utc, gps_products, object:{name, norad, gp_epoch_utc, perigee_alt_km, apogee_re}, gps_radius_km, pattern:{main_half_angle_deg, side_lobe_max_deg, earth_mask_alt_km, model, source}, receiver_note, t_h, radius_re, n_main, n_side, orbit_xyz_km, apogee_t_h, gps_xyz_at_apogee_km, gps_lobe_at_apogee, frac_time_4plus_main, frac_time_4plus_with_side}` |
| `walker_pnt.json` | `{generated_utc, config:{pattern, t, p, f, alt_km, inc_deg, source, force_model, integrator, mass_kg, drag_area_m2, cd, srp_area_m2, cr}, span_h, threads, wall_s_serial, wall_s_parallel, speedup, snapshot_xyz_km, planes, one_orbit_xyz_km, in_view:{lat_deg, walker_mean, gps_mean, el_mask_deg}, dop:{lat_deg, walker_pdop_median, gps_pdop_median, skipped:{walker, gps}, samples_per_lat}}` (a null median PDOP means no sample had 4 satellites in view) |
| `gravity_crossover.json` | `{generated_utc, machine:{cpu, threads, load_avg_1min_start, load_avg_1min_end}, model, model_file_bytes, max_degree_available, kernel, integrator, steps, passes, repeats_per_pass, stages_per_step, method, degrees, serial_us, parallel_us, serial_us_q25, serial_us_q75, parallel_us_q25, parallel_us_q75, overhead_us_degree2, auto_threshold_nmax, measured_crossover_nmax, crossover_range_nmax}` |
| `benchmarks.json` | `{generated_utc, brahe_version, benchmark_run_utc, statistic, source, tasks:[{name, label, results:[{library, language, median_s, ratio_to_brahe}]}]}` |

## Slide registry

| # | Label | Figure / data | Transition |
|---|---|---|---|
| 1 | Title | `gpsConstellation` / gps_constellation.json | fresh; orbits draw on, satellites fade in and loop over one period from the talk-time sample (75 s per period) |
| 2 | Sky Q | none | fresh; question alone (`data-flip="q-sky"`) |
| 2 | Sky plot | `skyplot`, `code-skyplot` / skyplot.json | magic move: question becomes the header; plot draws on, code card rises, count caption fades |
| 3 | Errors | none | fresh; two boxes |
| 3 | Errors 2 | none | continuation of Errors: measurement box dimmed, dynamics title moves (`dyn-title`) into a larger box that draws on, forces rise; click 1: the takeaway sentence |
| 4 | Tradeoff | `tradeoff` | fresh; property cards rise; click 1: question; clicks 2 to 4: one tool family row each (click 2 also shows the tendencies caption) |
| 5 | Quote | none | fresh; click 1: "I enjoy both, a lot." Holds hidden copies of the property cards at their Tradeoff positions as magic-move sources for the next slide |
| 6 | brahe | `check` x4 / facts from `BRAHE` in figs.js | magic move: property cards fly from their Tradeoff positions into a row; checks draw; facts and install line fade |
| 7 | Modules | `moduleMap` | fresh; cards rise one by one (overview for the module dividers) |
| 8 | Design choices | none | fresh; first panel on entry, clicks 1 to 3: one panel each |
| 9 | Quick TLE | `code-tle`, `groundTracks` / quick_hits.json, land.json, skyplot.json | fresh; code card rises, tracks draw on |
| 9 | Quick force model | `code-propagate`, `forceModelEffect` / quick_hits.json | fresh; curves draw on, labels fade |
| 9 | Quick frames | `code-frames`, `eciVsEcef` / quick_hits.json | fresh; both frames draw on together |
| 10 | Section Data | `moduleMap` (clone of Modules) | divider: data clients lit |
| 11 | TLE vs IGS | `code-tleSp3`, `tleVsSp3` / tle_vs_sp3.json | fresh; question as header, code card rises; click 1: R, T, N curves draw on (along-track in Cardinal) with RMS and largest difference |
| 12 | Section Time | `moduleMap` | divider: time and frames lit |
| 13 | Range mistake | `code-rangeEpochs`, `rangeMistake` / station_range.json | fresh; code card with `bh.GPS` (Palo Verde) and `bh.UTC` (Cardinal), question "How big is the error?"; click 1: satellite position error and GPS minus UTC; click 2: range error curve over the pass with its largest value |
| 14 | Section Orbits | `moduleMap` | divider: orbits and propagation lit |
| 15 | LEO receiver | `code-leoReceiver`, `leoLinks` / leo_receiver.json | fresh; code card with the ISS argument in Cardinal; Earth, ISS orbit and lines of sight to visible GPS satellites draw on, to scale |
| 15 | LEO counts | `leoCounts` / leo_receiver.json | fresh; ground series with mean; click 1: ISS series with mean, ground dims, comparison caption |
| 16 | Section Access | `moduleMap` | divider: access lit |
| 17 | MMS orbit | `mmsOrbit` / mms_visibility.json | fresh; question as header, orbit face-on to scale with GPS radius circle, main and side lobe half angles for one GPS satellite, Earth shadow; click 1: replay of MMS along the orbit with distance and counts in the readout (`data-readout`), "Geometric visibility, no link budget" |
| 17 | MMS counts | `mmsCounts` / mms_visibility.json | fresh; main-lobe counts against radius and its 4+ fraction; click 1: main or side lobes, main dims, second fraction and no-link-budget label |
| 18 | Section Walker | `moduleMap` | divider: orbits and propagation lit again |
| 19 | Walker build | `code-walker`, `walkerGlobe` / walker_pnt.json | fresh; planes draw on one by one, then satellites move (kinematic, one period per 20 s); click 1: serial, parallel, threads, speedup |
| 19 | Walker in view | `inViewByLat` / walker_pnt.json | fresh; GPS by latitude; click 1: Walker shell with inclination line, GPS dims, comparison sentence; cite is `config.source` |
| 20 | Section Speed | `moduleMap` | divider: propagation lit |
| 21 | Gravity | `gravityCrossover` / gravity_crossover.json | fresh; log-log axes, serial line with interquartile band draws on, serial values at the low and highest degree; click 1: parallel line and band (Lagunita) draw on, parallel values; click 2: brahe's automatic threshold as an exact vertical line, measured crossover range as a shaded band, sentence on the automatic switch |
| 22 | Benchmarks | `benchmarkRatios` / benchmarks.json | fresh; one panel per task in file order, bars from the brahe (Rust) 1x line to each library's median ratio on a shared log axis (brahe Python in Lagunita), key in the last row; panels fade in one by one |
| 23 | Adopters | `adopters` | fresh; nine logos plus Xona Space Systems and AWS by name, cells fade in |
| 24 | Next | none | fresh; roadmap panel; click 1: the request for shareable orbital observations |
| 25 | Links | `closeLinks` | fresh; two QR codes side by side at the same size, each with its label and URLs beneath: brahe (`img/brahe-qr.webp`, brahe.space and github.com/duncaneddy/brahe) and the talk repository (`img/repo-qr.webp`, github.com/duncaneddy/2026_spnt_symposium) |
| B | Backup | none | divider |
| B1 | Pseudorange | none / station_range.json (`terms_m`) | fresh; equation and geometric range; clicks 1 to 3: light time, Earth rotation (the three rows that sum to rho), satellite clock |
| B2 | PDOP | `pdopByLat` / walker_pnt.json (`dop`) | fresh; GPS median PDOP by latitude (log); click 1: Walker shell with a gap and label where the median is null, GPS dims, skipped-sample counts |
| B3 | Events | `code-valueEvent` | fresh; brahe example custom_value_event.py |
| B4 | Extensible dynamics | `code-additionalDynamics`, `code-sensitivity` | fresh; brahe examples battery_tracking.py and sensitivity_analysis.py |
| B5 | Property computer | `code-propertyComputer`, `code-propertyAccess` | fresh; brahe example custom_property_computer.py (class, and the access call), note that access takes ground locations |
| B6 | History | none | fresh; two panels: examples and tests in CI, tests and LLM-assisted maintenance |

## Deck implementation

- Shell: `deck/js/deck.js` (stage scaling, keys, hash routing, chrome, continuations, entry choreography, FLIP).
- Strokes: `deck/js/sketch.js` (seeded hand-drawn lines, boxes and ellipses; `[data-rough]` auto-decoration,
  seed from `data-rough-key` or text so clones redraw identically).
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
- Code cards: `codeCard(el, lines, {highlight, steps, size, key})` in figs.js draws monospace Python in a
  hand-drawn box as wide as `el`; brahe calls (`bh.*`) in Lagunita. `highlight: [n]` draws line n in
  Cardinal; `highlight: [[n, k]]` turns line n Cardinal on click k; `steps: {n: k}` hides line n until
  click k. Slide code lives in the `CODE` table (`key: {needs, lines, opts}`); each entry is registered as
  figure `code-<key>` and shows the data-pending note while its JSON is missing. Lines are real script
  lines, trimmed and wrapped at Python continuation points, at most 63 characters for a 900 px card at
  22 px.
- Module map: `figures.moduleMap` renders one card per entry of `MODULES` (keys `time`, `frames`,
  `orbits`, `propagation`, `access`, `data`, `estimation`). Divider slide:
  `<section class="slide" data-label="Section X" data-clone="Modules" data-lc-current="data">` (several
  keys comma separated, e.g. `"time,frames"`). Current cards turn Cardinal, cards current on an earlier
  divider turn gray, the rest stay ink; moving between adjacent dividers animates the colors.
- Magic moves of hand-drawn boxes: put the outline on an inner element and `data-flip` on a positioned
  wrapper (see `.prop-slot`), so the outline moves with the card.
- Code card token colors: `marks: [[line, 'text', 'cardinal' | 'green']]` in a `CODE` entry's `opts`
  colors that text on that line (one mark per line).
- Figures revealed on a click: put `data-step="n"` on the `.fig` div and start draw-ons with
  `whenShown(el, fn)`, which runs fn now or on the click that reveals el. `dimFromStep(el, g, n, op)`
  dims a group from step n onward in both directions. Comparison charts (`leoCounts`, `mmsCounts`,
  `inViewByLat`) show the familiar series first and add the new one on click 1 with the first dimmed.
- Replays: `mmsOrbit` (replay starts on click 1, or on arrival when the slide is entered fully built)
  and `walkerGlobe` (kinematic: each satellite rotates along its own plane at the shell's orbital rate,
  one period per 20 s) return cancel functions. With reduced motion, `mmsOrbit` stays at the apogee
  sample and `walkerGlobe` at the start epoch. `mmsOrbit` writes its readout into the slide's
  `[data-readout="r|main|side"]` fields.

## Needed from Duncan

- `deck/img/logos/xona.png` (or svg): Xona Space Systems logo for the adopters slide (shown by name until then).
- `deck/img/logos/aws.png` (or svg): AWS logo for the adopters slide (shown by name until then).
