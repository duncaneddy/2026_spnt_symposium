# /// script
# requires-python = ">=3.12"
# dependencies = ["brahe @ git+https://github.com/duncaneddy/brahe@3e2ed7c1739b3f372c35c708702246bbee831183", "numpy"]
# ///
"""Output and run time of the module snippets shown on the slides.

Runs each deck/snippets/mod_*.py in a fresh Python process RUNS times and records what it
prints and how long it takes. The run time is the wall-clock time of the snippet body in a
process that has already imported brahe and numpy, so it excludes interpreter start and the
imports, and includes everything the snippet does: loading Earth orientation data, and for
mod_data reading the product listing and orbit file from brahe's local cache, or the network
requests to the IGS mirror when they are not cached yet. The median of the runs is reported,
so it reflects cached access.

Run:
  uv run scripts/snippet_outputs.py [--out path.json]

Output (deck/data/snippet_outputs.json):
  {generated_utc, runs, machine, snippets:{<name>:{stdout:[line, ...], seconds}}}
"""

import argparse
import json
import platform
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "deck/data/snippet_outputs.json"
SNIPPETS = sorted((ROOT / "deck/snippets").glob("mod_*.py"))
RUNS = 3

CHILD = """
import contextlib, io, json, sys, time
import brahe, numpy
code = compile(open(sys.argv[1]).read(), sys.argv[1], "exec")
buffer = io.StringIO()
with contextlib.redirect_stdout(buffer):
    start = time.perf_counter()
    exec(code, {"__name__": "__main__"})
    seconds = time.perf_counter() - start
print(json.dumps({"stdout": buffer.getvalue(), "seconds": seconds}))
"""


def run_once(path: Path) -> dict:
    done = subprocess.run([sys.executable, "-c", CHILD, str(path)], capture_output=True, text=True, check=True)
    return json.loads(done.stdout.splitlines()[-1])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    out = parser.parse_args().out

    snippets = {}
    for path in SNIPPETS:
        runs = [run_once(path) for _ in range(RUNS)]
        stdout = runs[-1]["stdout"].rstrip("\n").split("\n")
        assert all(r["stdout"] == runs[-1]["stdout"] for r in runs), f"{path.name}: output differs between runs"
        assert stdout != [""], f"{path.name}: no output"
        seconds = statistics.median(r["seconds"] for r in runs)
        snippets[path.stem] = {"stdout": stdout, "seconds": float(f"{seconds:.3g}")}
        print(f"{path.stem}: {seconds * 1e3:.1f} ms\n  " + "\n  ".join(stdout))

    result = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "runs": RUNS,
        "machine": f"{platform.system()} {platform.machine()}",
        "snippets": snippets,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, separators=(",", ":")))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
