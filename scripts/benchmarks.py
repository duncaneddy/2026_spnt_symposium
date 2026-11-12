# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Cross-library timing comparison for the tasks a GNSS analysis leans on.

Reads the headline results of the brahe comparative benchmark suite
(benchmarks/comparative in the brahe repository) and keeps, for a handful of
tasks relevant to navigation work, one timing per library and language.

Statistic:
  The suite records the wall-clock time of every iteration of a task
  (200 iterations per library, same inputs for every library) in
  `times_seconds`. Its report tables list the median alongside the mean; this
  script uses the median, which is robust to warm-up and scheduler outliers.
  Times are seconds per task invocation, as defined by the benchmark task
  (see benchmarks/comparative/tasks), identical across libraries.

Ratios:
  ratio_to_brahe = library median / brahe (Rust) median for the same task.
  A value above 1 means the library is slower than brahe; below 1 means it is
  faster. brahe's Python bindings are included as their own row, with the same
  Rust reference, so the slide can show both.

Kept tasks:
  time.utc_to_gps, coordinates.geodetic_to_ecef, coordinates.ecef_to_azel,
  frames.state_eci_to_ecef, propagation.sgp4_trajectory,
  propagation.numerical_rk4_grav20x20_sun_moon, access.sgp4_access.

Run:
  uv run scripts/benchmarks.py [--results path/to/run_latest.json] [--out path.json]

Output (deck/data/benchmarks.json):
  {generated_utc, brahe_version, benchmark_run_utc, statistic, source,
   tasks:[{name, label, results:[{library, language, median_s, ratio_to_brahe}]}]}
  Results within a task are sorted fastest first.
"""

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "deck/data/benchmarks.json"
DEFAULT_RESULTS = Path("~/repos/brahe/benchmarks/comparative/results/run_latest.json").expanduser()
SOURCE = "benchmarks/comparative/results/run_latest.json"

TASKS = {
    "time.utc_to_gps": "UTC to GPS time conversion",
    "coordinates.geodetic_to_ecef": "Geodetic to ECEF position",
    "coordinates.ecef_to_azel": "ECEF to azimuth/elevation",
    "frames.state_eci_to_ecef": "ECI to ECEF state transformation",
    "propagation.sgp4_trajectory": "SGP4 trajectory propagation",
    "propagation.numerical_rk4_grav20x20_sun_moon": "Numerical propagation, 20x20 gravity + Sun/Moon",
    "access.sgp4_access": "Ground-station access windows (SGP4)",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def build_task(name: str, runs: list[dict]) -> dict:
    """One task entry: median per library/language with ratio to brahe (Rust)."""
    medians = {
        (r["library"], r["language"]): statistics.median(r["times_seconds"]) for r in runs
    }
    reference = medians[("brahe", "rust")]
    results = [
        {
            "library": library,
            "language": language,
            "median_s": median,
            "ratio_to_brahe": median / reference,
        }
        for (library, language), median in sorted(medians.items(), key=lambda kv: kv[1])
    ]
    return {"name": name, "label": TASKS[name], "results": results}


def main() -> None:
    args = parse_args()
    if not args.results.is_file():
        sys.exit(f"benchmark results not found: {args.results} (pass --results or check out brahe)")
    run = json.loads(args.results.read_text())

    by_task: dict[str, list[dict]] = {name: [] for name in TASKS}
    for result in run["task_results"]:
        if result["task_name"] in by_task:
            by_task[result["task_name"]].append(result)

    tasks = [build_task(name, runs) for name, runs in by_task.items()]

    brahe_version = run["system_info"]["brahe_version"]
    assert brahe_version, "brahe_version missing from benchmark results"
    for task in tasks:
        libs = {(r["library"], r["language"]) for r in task["results"]}
        assert ("brahe", "rust") in libs, f"{task['name']}: no brahe (Rust) result"
        assert any(lib != "brahe" for lib, _ in libs), f"{task['name']}: no other library"
        assert all(r["ratio_to_brahe"] > 0 for r in task["results"]), f"{task['name']}: bad ratio"

    out = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "brahe_version": brahe_version,
        "benchmark_run_utc": run["timestamp"],
        "statistic": "median of per-iteration wall-clock time, 200 iterations",
        "source": SOURCE,
        "tasks": tasks,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2) + "\n")

    for task in tasks:
        print(task["label"])
        for r in task["results"]:
            print(f"  {r['library']:9s}{r['language']:9s}{r['median_s']:12.3e} s  x{r['ratio_to_brahe']:8.2f}")


if __name__ == "__main__":
    main()
