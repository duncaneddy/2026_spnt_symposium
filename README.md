# Practical Astrodynamics: Open-Source Tools for Constellation Analysis and Design

Talk at the 2026 Stanford Center for Position, Navigation and Time (SPNT) Symposium, November 12, 2026.

The slides are a single HTML page in `deck/`. Every figure is drawn from data produced by a small
standalone script in `scripts/`, built on the open-source [brahe](https://github.com/duncaneddy/brahe)
astrodynamics library. Each script runs on its own with [uv](https://docs.astral.sh/uv/).

## Running the scripts

```bash
uv run scripts/<name>.py
```

Each script writes `deck/data/<name>.json`. To regenerate every data file except the benchmarks, in
dependency order:

```bash
just data
```

`benchmarks.json` is built separately, because it reads results from a brahe checkout:

```bash
just benchmarks                                    # reads ~/repos/brahe
just benchmarks --results path/to/run_latest.json  # or any results file
```

The `justfile` recipes are `data`, `benchmarks`, `run <name>` (one script), `serve` and `snippets`.

- **brahe version:** the scripts pin brahe to a commit on its main branch that includes the IGS/SP3
  orbit product client, until a released version with that client is published. The pin builds brahe
  from source, so the first run needs a Rust toolchain and takes several minutes; later runs reuse the
  build.
- **Space-Track credentials:** GP element sets come from CelesTrak. When CelesTrak is unreachable the
  scripts fall back to Space-Track, which needs an account, read from the environment variables
  `SPACETRACK_USER` and `SPACETRACK_PASS`. They are not needed while CelesTrak responds.
- **`benchmarks.py`** reads the results of brahe's comparative benchmark suite from a brahe checkout
  (`~/repos/brahe/benchmarks/comparative/results/run_latest.json` by default; pass `--results` for
  another path), so it is not part of `just data`.
- **IGS orbit products** come from the BKG mirror of the IGS archive, which needs no login.

Downloads are cached under `deck/data/raw/`, so the deck does not need the network during the talk.

| Script | What it computes |
|---|---|
| `basemap.py` | Natural Earth 1:110m land outline as longitude/latitude polylines, for the maps |
| `skyplot.py` | Azimuth and elevation of every GPS satellite from the Stanford campus at the talk time, from an IGS ultra-rapid orbit, with tracks one hour either side |
| `three_levels.py` | The same sky-plot question answered three ways (Keplerian orbits on a spinning sphere, TLEs with SGP4, the IGS orbit product), with the count above the mask and the position and sky-direction errors of the two simpler answers |
| `gps_constellation.py` | Every GPS satellite's position in GCRF over one orbital period, from the IGS ultra-rapid orbit, for the title animation |
| `quick_hits.py` | Three short examples: GPS ground tracks from public GP elements with SGP4, two-body against full force-model propagation, and one GPS orbit in GCRF and ITRF |
| `tle_vs_sp3.py` | Difference between SGP4 from the public GP elements and the IGS orbit for one GPS satellite, in radial, along-track and cross-track components |
| `station_range.py` | Range from Stanford to a GPS satellite over its pass, the error from labeling GPS time as UTC, and the pseudorange terms at the reference instant |
| `leo_receiver.py` | GPS satellites in view of a receiver on the ground and on the ISS, from one visibility function called with each receiver |
| `mms_visibility.py` | GPS satellites usable by MMS 1 over one orbit through the transmit antenna main lobe and through the main or side lobes, with Earth blockage |
| `walker_pnt.py` | A LEO PNT Walker shell propagated serially and in parallel with a numerical force model, and satellites in view and PDOP by latitude against GPS |
| `gravity_crossover.py` | Time per spherical-harmonic gravity evaluation against degree, with brahe's parallel mode forced off and on, measured through the numerical propagator |
| `benchmarks.py` | Median run time of common tasks in brahe and other open-source libraries, relative to brahe, from brahe's comparative benchmark suite |

## Code on the slides

Every code card in the deck is a complete program in `deck/snippets/`, shown on its slide as the file
reads below its PEP 723 header (the deck loads the files directly), except for a few lines each card
leaves out (alias constants and the closing `print`). Each runs on its own and prints
its result:

```bash
uv run deck/snippets/<name>.py
just snippets        # run them all
```

They are short versions of the analysis scripts in `scripts/` and of examples in the brahe repository,
formatted with `uvx ruff format --line-length 68 deck/snippets`. The snippets that read GP elements
(`ground_tracks.py`, `tle_vs_sp3.py`, `leo_receiver.py`) download them from CelesTrak, so their results
follow the current element sets.

## Viewing the slides

```bash
just serve
```

Then open <http://localhost:8280>. Keys: arrows or space to move, `n` for speaker notes, `b` to
jump to backup slides, `r` to replay the current slide's animation, `f` for full screen, and a
slide number followed by Enter to jump to that slide.

Fonts (Source Serif 4, Source Sans 3, Source Code Pro) and KaTeX are bundled in `deck/fonts/` and
`deck/vendor/`, so the deck loads with no network access.

## Third-party material

- **Fonts:** Source Serif 4, Source Sans 3 and Source Code Pro (Adobe), in `deck/fonts/`, under the
  SIL Open Font License 1.1.
- **KaTeX**, in `deck/vendor/katex/`, under the MIT License.
- **Land outline:** Natural Earth 1:110m land, public domain (`scripts/basemap.py`).
- **Logos:** the company logos in `deck/img/logos/` and the Stanford logos in `deck/img/` are
  trademarks of their owners, used here for identification.

The bundled font and KaTeX files do not include separate license files.
