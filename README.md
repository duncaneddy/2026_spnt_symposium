# Practical Astrodynamics: Open-Source Tools for Constellation Analysis and Design

Talk at the 2026 Stanford Center for Position, Navigation and Time (SPNT) Symposium, November 12, 2026.

The slides are a single HTML page in `deck/`. Every figure is drawn from data produced by a small
standalone script in `scripts/`, built on the open-source [brahe](https://github.com/duncaneddy/brahe)
astrodynamics library. Each script runs on its own with [uv](https://docs.astral.sh/uv/); no
environment setup is needed beyond a Rust toolchain on first run, because the scripts pin brahe to a
git branch.

## Running the scripts

```bash
uv run scripts/skyplot.py
```

Each script writes `deck/data/<name>.json`. To regenerate everything:

```bash
just data
```

Downloads are cached under `deck/data/raw/`, so the deck does not need the network during the talk.

| Script | What it computes |
|---|---|

## Viewing the slides

```bash
just serve
```

Then open <http://localhost:8280>. Keys: arrows or space to move, `n` for speaker notes, `b` to
jump to backup slides, `r` to replay the current slide's animation, `f` for full screen, and a
slide number followed by Enter to jump to that slide.

Fonts (Source Serif 4, Source Sans 3, Source Code Pro) and KaTeX are bundled in `deck/fonts/` and
`deck/vendor/`, so the deck loads with no network access.
