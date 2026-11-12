# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Cross-library timing comparison for the tasks a GNSS analysis leans on.

Reads the headline results of the brahe comparative benchmark suite
(benchmarks/comparative in the brahe repository) and keeps, for a handful of
tasks relevant to navigation work, one timing per library and language. The
default input is a brahe checkout; `--results` also accepts the comparative
run of the Brahe-and-Astrojax-JAIS- paper repository
(reproducibility/results/comparative/run_latest.json), which uses the same
harness and file format with more libraries (OSTk, FreeFlyer).

Statistic:
  The suite records the wall-clock time of every iteration of a task
  (200 iterations per library, same inputs for every library) in
  `times_seconds`. Its report tables list the median alongside the mean; this
  script uses the median, which is robust to warm-up and scheduler outliers.
  Times are seconds per task invocation, as defined by the benchmark task
  (see benchmarks/comparative/tasks), identical across libraries. One
  invocation processes a batch of inputs (`batch` in the output).

Ratios:
  ratio_to_brahe = library median / brahe (Rust) median for the same task.
  A value above 1 means the library is slower than brahe; below 1 means it is
  faster. brahe's Python bindings are included as their own row, with the same
  Rust reference.

Kept tasks:
  time.utc_to_gps, coordinates.geodetic_to_ecef, frames.state_eci_to_ecef,
  propagation.sgp4_trajectory, access.sgp4_access,
  propagation.numerical_rk4_grav20x20_sun_moon,
  propagation.numerical_rk4_grav80x80_full.
  `faster_elsewhere` lists every task in the run, kept or not, where another
  library's median is below brahe (Rust)'s.

Libraries that start a process per call:
  FreeFlyer runs one subprocess per invocation, so every median includes a
  process launch. Its smallest median over the run is taken as that launch
  time. It is kept in a task's results, flagged `launch_per_call`, only where
  its median is at least LAUNCH_MIN_RATIO times the launch time, and it is
  left out of `faster_elsewhere`. `launch_per_call` reports the launch time,
  the ratio and the library version.

Run:
  uv run scripts/benchmarks.py [--results path/to/run_latest.json] [--out path.json]
      [--source "repository: path"] [--hardware "..."] [--brahe-build "..."]

Output (deck/data/benchmarks.json):
  {generated_utc, brahe_version, brahe_build, benchmark_run_utc, statistic,
   iterations, source, hardware, library_versions,
   launch_per_call:{<library>:{version, launch_s, min_ratio}}, tasks_in_run,
   tasks:[{name, label, batch, results:[{library, language, median_s, ratio_to_brahe,
                                         launch_per_call?}]}],
   faster_elsewhere:[{task, library, ratio_to_brahe}]}
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
SOURCE = "brahe: benchmarks/comparative/results/run_latest.json"
LAUNCH_PER_CALL = ("freeflyer",)
LAUNCH_MIN_RATIO = 1.5

# Task name -> (slide label, inputs per timed invocation, from the task definitions).
TASKS = {
    "time.utc_to_gps": ("UTC to GPS time conversion", "50 epochs"),
    "coordinates.geodetic_to_ecef": ("Geodetic to ECEF position", "50 positions"),
    "frames.state_eci_to_ecef": ("ECI to ECEF state transformation", "50 states"),
    "propagation.sgp4_trajectory": ("SGP4 trajectory propagation", "1 day at 60 s"),
    "access.sgp4_access": ("Ground-station access windows", "100 sites, 1 day"),
    "propagation.numerical_rk4_grav20x20_sun_moon": (
        "Numerical propagation, 20x20 gravity, Sun and Moon",
        "about one LEO orbit",
    ),
    "propagation.numerical_rk4_grav80x80_full": (
        "Numerical propagation, 80x80 gravity, Sun, Moon, drag and SRP",
        "about one LEO orbit",
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--source", default=SOURCE, help="repository and path of the results file")
    parser.add_argument("--hardware", default=None, help="machine description (default: from system_info)")
    parser.add_argument("--brahe-build", default=None, help="how the benchmarked brahe was built")
    return parser.parse_args()


def build_task(name: str, medians: dict[tuple[str, str], float], launch_s: dict[str, float]) -> dict:
    """One task entry: median per library/language with ratio to brahe (Rust). A library that
    starts a process per call is kept only where its median clears its launch time."""
    reference = medians[("brahe", "rust")]
    results = [
        {
            "library": library,
            "language": language,
            "median_s": median,
            "ratio_to_brahe": median / reference,
        }
        | ({"launch_per_call": True} if library in launch_s else {})
        for (library, language), median in sorted(medians.items(), key=lambda kv: kv[1])
        if library not in launch_s or median >= LAUNCH_MIN_RATIO * launch_s[library]
    ]
    label, batch = TASKS[name]
    return {"name": name, "label": label, "batch": batch, "results": results}


def main() -> None:
    args = parse_args()
    if not args.results.is_file():
        sys.exit(f"benchmark results not found: {args.results} (pass --results or check out brahe)")
    run = json.loads(args.results.read_text())
    info = run["system_info"]

    by_task: dict[str, dict[tuple[str, str], float]] = {}
    for r in run["task_results"]:
        by_task.setdefault(r["task_name"], {})[(r["library"], r["language"])] = statistics.median(r["times_seconds"])

    launch_s = {}
    for lib in LAUNCH_PER_CALL:
        lib_medians = [median for meds in by_task.values() for (name, _), median in meds.items() if name == lib]
        if lib_medians:
            launch_s[lib] = min(lib_medians)

    tasks = [build_task(name, by_task[name], launch_s) for name in TASKS]

    faster = [
        {"task": name, "library": lib, "ratio_to_brahe": median / meds[("brahe", "rust")]}
        for name, meds in sorted(by_task.items())
        if meds.get(("brahe", "rust"), 0) > 0
        for (lib, _), median in sorted(meds.items(), key=lambda kv: kv[1])
        if lib != "brahe" and lib not in launch_s and median < meds[("brahe", "rust")]
    ]

    versions = {}
    for r in run["task_results"]:
        version = r.get("metadata", {}).get("version")
        if r["library"] != "brahe" and version and version.lower() != r["library"]:
            versions[r["library"]] = version

    launch_per_call = {
        lib: {"version": versions.get(lib), "launch_s": seconds, "min_ratio": LAUNCH_MIN_RATIO}
        for lib, seconds in launch_s.items()
    }

    iterations = {r["iterations"] for r in run["task_results"] if r["task_name"] in TASKS}

    brahe_version = info["brahe_version"]
    assert brahe_version, "brahe_version missing from benchmark results"
    assert len(iterations) == 1, f"mixed iteration counts: {iterations}"
    for task in tasks:
        libs = {(r["library"], r["language"]) for r in task["results"]}
        assert ("brahe", "rust") in libs, f"{task['name']}: no brahe (Rust) result"
        assert any(lib != "brahe" for lib, _ in libs), f"{task['name']}: no other library"
        assert all(r["ratio_to_brahe"] > 0 for r in task["results"]), f"{task['name']}: bad ratio"
        for r in task["results"]:
            if r["library"] in launch_s:
                assert r["median_s"] >= LAUNCH_MIN_RATIO * launch_s[r["library"]], f"{task['name']}: launch-bound result"

    out = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "brahe_version": brahe_version,
        "brahe_build": args.brahe_build,
        "benchmark_run_utc": run["timestamp"],
        "statistic": "median of per-iteration wall-clock time",
        "iterations": iterations.pop(),
        "source": args.source,
        "hardware": args.hardware or f"{info['platform']}, {info['cpu_count']} CPUs",
        "library_versions": {k: versions[k] for k in sorted(versions)},
        "launch_per_call": launch_per_call,
        "tasks_in_run": len(by_task),
        "tasks": tasks,
        "faster_elsewhere": faster,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2) + "\n")

    for task in tasks:
        print(f"{task['label']} ({task['batch']})")
        for r in task["results"]:
            print(f"  {r['library']:9s}{r['language']:9s}{r['median_s']:12.3e} s  x{r['ratio_to_brahe']:8.2f}")
    print("Another library faster than brahe (Rust):")
    for f in faster:
        print(f"  {f['task']:48s}{f['library']:9s}x{f['ratio_to_brahe']:8.3f}")


if __name__ == "__main__":
    main()
