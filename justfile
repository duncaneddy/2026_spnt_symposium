scripts := "basemap skyplot three_levels gps_constellation quick_hits tle_vs_sp3 station_range leo_receiver mms_visibility walker_pnt gravity_crossover"

# Regenerate every data file except benchmarks.json
data:
    for s in {{scripts}}; do uv run scripts/$s.py || exit 1; done

# Rebuild benchmarks.json from a comparative benchmark results file, e.g. `just benchmarks path/to/run_latest.json --hardware "..."`
[positional-arguments]
benchmarks results *args:
    uv run scripts/benchmarks.py --results "$@"

# Run one analysis script, e.g. `just run skyplot`
run name:
    uv run scripts/{{name}}.py

# Serve the deck at http://localhost:8280
serve:
    uv run scripts/serve.py 8280

# Run every code snippet shown on the slides
snippets:
    for f in deck/snippets/*.py; do echo "$f"; uv run "$f" || exit 1; done
