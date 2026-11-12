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
10. Data clients. IGS SP3 download. [Q] "How far is the public TLE from the SP3 orbit?" [S:tle_vs_sp3]
11. Time and frames. Station to GPS range, then GPS time read as UTC. [Q] "How big is the error?" [S:station_range]
12. Composable. Receiver moves to LEO: one line changes. [S:leo_receiver]
13. MMS. [Q] "Can you use GPS from above the GPS constellation?" Transmit antenna pattern, Earth blockage,
    custom access property computer. [S:mms_visibility]
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
`["brahe @ git+https://github.com/duncaneddy/brahe@sp3/9-igs-rate-limit", "numpy"]`, runnable as
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

## Needed from Duncan

- `deck/img/logos/xona.png` (or svg): Xona Space Systems logo for the adopters slide.
- `deck/img/logos/aws.png` (or svg): AWS logo for the adopters slide.
- QR code image for `github.com/duncaneddy/2026_spnt_symposium` (the closing slide shows the URL as text until then).
