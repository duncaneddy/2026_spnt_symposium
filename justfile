scripts := ""

# Regenerate every data file the deck uses
data:
    for s in {{scripts}}; do uv run scripts/$s.py || exit 1; done

# Run one analysis script, e.g. `just run skyplot`
run name:
    uv run scripts/{{name}}.py

# Serve the deck at http://localhost:8280
serve:
    uv run scripts/serve.py 8280
