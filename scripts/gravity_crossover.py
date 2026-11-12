# /// script
# requires-python = ">=3.12"
# dependencies = ["brahe @ git+https://github.com/duncaneddy/brahe@sp3/9-igs-rate-limit", "numpy"]
# ///
"""Serial versus parallel spherical-harmonic gravity cost in brahe's propagator.

Times a gravity-only NumericalOrbitPropagator (fixed-step RK4, one LEO orbit
state) for a sweep of spherical-harmonic degree = order, once with
ParallelMode.Never and once with ParallelMode.Always, and reports the wall
time per gravity evaluation: elapsed / (steps x 4 RK4 stages).

What is timed:
  - propagate_to() on a fresh propagator. Construction and model loading are
    not timed. Each pass runs, per degree, one discarded warm-up per mode and
    then REPEATS runs that alternate Never and Always so drift affects both
    modes evenly. The sweep is repeated for PASSES passes.
  - The time per evaluation therefore includes the integrator arithmetic and
    the ECI-to-ECEF rotation that brahe performs on every force evaluation. That
    overhead is the same in both modes; the degree-2 value (OVERHEAD_NMAX) is
    recorded as an estimate of it. It is not a bare acceleration call: brahe's
    Python acceleration functions always use ParallelMode.Auto, so the two
    kernels can only be forced through GravityConfiguration(parallel=...).

Which code runs (brahe src/orbit_dynamics/gravity.rs, src/propagators):
  - The propagator calls accel_gravity_spherical_harmonics, which dispatches to
    the Clenshaw kernel (GravityModel::compute_spherical_harmonics) for a model
    with Clenshaw tables, the default.
  - The kernel choice is GravityModel::compute_spherical_harmonics (Clenshaw
    when the model carries Clenshaw tables, which is the default for every
    model built by from_model_type / from_file) and the threshold is
    CLENSHAW_PARALLEL_THRESHOLD_NMAX, both in src/orbit_dynamics/gravity.rs;
    brahe's Python API does not expose a check of either.
  - should_parallelize_clenshaw: Never is always serial, Always is always
    parallel on brahe's managed rayon pool, Auto parallelizes only when
    n_max >= CLENSHAW_PARALLEL_THRESHOLD_NMAX (180). That constant is recorded
    as auto_threshold_nmax.

Model:
  - EGM96 (degree and order 360) from ICGEM, cached in
    deck/data/raw/gravity_crossover/. brahe's packaged EGM2008 stops at degree
    120, which is below the Auto threshold.

Frames and time: initial state is ECI (GCRF), epoch UTC; the gravity field is
evaluated in the Earth-fixed frame and rotated back, all inside brahe.

Run:
  uv run scripts/gravity_crossover.py [--out path.json]

Output (deck/data/gravity_crossover.json):
  {generated_utc, machine:{cpu, threads, load_avg_1min_start, load_avg_1min_end},
   model, model_file_bytes, max_degree_available, kernel, integrator, steps,
   stages_per_step, passes, repeats_per_pass, method, degrees, serial_us,
   parallel_us, serial_us_q25, serial_us_q75, parallel_us_q25, parallel_us_q75,
   overhead_us_degree2, auto_threshold_nmax, measured_crossover_nmax,
   crossover_range_nmax}
  threads is the size of brahe's rayon thread pool (bh.get_max_threads()).
  serial_us / parallel_us are the medians, and the q25 / q75 fields the
  quartiles, of microseconds per gravity evaluation pooled over all passes.
  measured_crossover_nmax: take the first degree from which parallel stays
  faster than serial through the end of the sweep and the degree before it;
  the crossover is the zero of (parallel - serial), linearly interpolated
  between those two degrees and rounded to an integer degree. null if parallel
  is not faster at the highest degree. crossover_range_nmax is [min, max] of
  the same quantity computed from each pass's own medians (null entries are
  ignored; null if no pass has a crossover).
"""

import argparse
import json
import os
import platform
import statistics
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import brahe as bh
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "deck/data/gravity_crossover.json"
RAW_DIR = ROOT / "deck/data/raw/gravity_crossover"
MODEL_FILE = RAW_DIR / "EGM96.gfc"
MODEL_URL = (
    "https://icgem.gfz.de/getmodel/gfc/"
    "971b0a3b49a497910aad23cd85e066d4cd9af0aeafe7ce6301a696bed8570be3/EGM96.gfc"
)
MODEL_NAME = "EGM96"
MAX_DEGREE_AVAILABLE = 360

DEGREES = [2, 10, 20, 50, 90, 120, *range(150, 261, 10), 300, 360]
OVERHEAD_NMAX = 2
AUTO_THRESHOLD_NMAX = 180
STEP_S = 10.0
STEPS = 200
STAGES_PER_STEP = 4
REPEATS = 15
PASSES = 3

EPOCH = bh.Epoch(2026, 11, 12, 19, 0, 0.0, 0.0, time_system=bh.UTC)
ORBIT = np.array([bh.R_EARTH + 550e3, 0.001, 53.0, 15.0, 30.0, 45.0])


def ensure_model() -> Path:
    if not MODEL_FILE.exists():
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        tmp = MODEL_FILE.with_suffix(".gfc.part")
        with urllib.request.urlopen(MODEL_URL, timeout=120) as resp:
            tmp.write_bytes(resp.read())
        tmp.replace(MODEL_FILE)
    return MODEL_FILE


def cpu_name() -> str:
    if platform.system() == "Darwin":
        return subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True
        ).stdout.strip()
    return platform.processor() or platform.machine()


def propagation_time_s(model_type: bh.GravityModelType, degree: int, mode: bh.ParallelMode) -> float:
    force_model = bh.ForceModelConfig(
        gravity=bh.GravityConfiguration(
            degree=degree, order=degree, model_type=model_type, parallel=mode
        )
    )
    config = bh.NumericalPropagationConfig(
        bh.IntegrationMethod.RK4,
        bh.IntegratorConfig.fixed_step(STEP_S),
        bh.VariationalConfig(),
    )
    state = bh.state_koe_to_eci(ORBIT, bh.AngleFormat.DEGREES)
    prop = bh.NumericalOrbitPropagator(EPOCH, state, config, force_model)
    t0 = time.perf_counter()
    prop.propagate_to(EPOCH + STEPS * STEP_S)
    return time.perf_counter() - t0


def eval_us(model_type: bh.GravityModelType, degree: int, mode: bh.ParallelMode) -> float:
    return propagation_time_s(model_type, degree, mode) / (STEPS * STAGES_PER_STEP) * 1e6


def sweep_pass(model_type: bh.GravityModelType) -> tuple[list[list[float]], list[list[float]]]:
    serial, parallel = [], []
    for n in DEGREES:
        eval_us(model_type, n, bh.ParallelMode.Never)
        eval_us(model_type, n, bh.ParallelMode.Always)
        s_runs, p_runs = [], []
        for _ in range(REPEATS):
            s_runs.append(eval_us(model_type, n, bh.ParallelMode.Never))
            p_runs.append(eval_us(model_type, n, bh.ParallelMode.Always))
        serial.append(s_runs)
        parallel.append(p_runs)
    return serial, parallel


def crossover(degrees: list[int], serial: list[float], parallel: list[float]) -> int | None:
    first = len(degrees)
    while first > 0 and parallel[first - 1] < serial[first - 1]:
        first -= 1
    if first == len(degrees):
        return None
    if first == 0:
        return degrees[0]
    d0 = parallel[first - 1] - serial[first - 1]
    d1 = parallel[first] - serial[first]
    frac = d0 / (d0 - d1)
    return round(degrees[first - 1] + frac * (degrees[first] - degrees[first - 1]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    bh.initialize_eop()
    model_type = bh.GravityModelType.from_file(str(ensure_model()))

    load_start = os.getloadavg()[0]
    pooled_s = [[] for _ in DEGREES]
    pooled_p = [[] for _ in DEGREES]
    pass_crossovers = []
    for k in range(PASSES):
        serial, parallel = sweep_pass(model_type)
        for i in range(len(DEGREES)):
            pooled_s[i] += serial[i]
            pooled_p[i] += parallel[i]
        pass_crossovers.append(
            crossover(
                DEGREES,
                [statistics.median(r) for r in serial],
                [statistics.median(r) for r in parallel],
            )
        )
        print(f"pass {k + 1}: crossover {pass_crossovers[-1]}")

    def stat(runs: list[list[float]], q: int | None) -> list[float]:
        if q is None:
            return [statistics.median(r) for r in runs]
        return [statistics.quantiles(r, n=4)[q] for r in runs]

    serial_us, parallel_us = stat(pooled_s, None), stat(pooled_p, None)
    for n, s_, p_ in zip(DEGREES, serial_us, parallel_us):
        print(f"n={n:4d}  serial {s_:9.2f} us  parallel {p_:9.2f} us")

    i10, ilast = DEGREES.index(10), -1
    assert parallel_us[i10] > serial_us[i10], "parallel should be slower than serial at degree 10"
    assert all(t > 0 for t in serial_us + parallel_us)
    assert all(b >= 0.8 * a for a, b in zip(serial_us, serial_us[1:])), "serial_us should be non-decreasing within 20%"
    if DEGREES[ilast] == 360:
        assert parallel_us[ilast] < serial_us[ilast], "parallel should be faster at degree 360"

    result = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "machine": {"cpu": cpu_name(), "threads": bh.get_max_threads(), "load_avg_1min_start": load_start, "load_avg_1min_end": os.getloadavg()[0]},
        "model": MODEL_NAME,
        "model_file_bytes": MODEL_FILE.stat().st_size,
        "max_degree_available": MAX_DEGREE_AVAILABLE,
        "kernel": "Clenshaw",
        "integrator": f"RK4 fixed step {STEP_S:g} s",
        "steps": STEPS,
        "passes": PASSES,
        "repeats_per_pass": REPEATS,
        "stages_per_step": STAGES_PER_STEP,
        "method": (
            "Wall time of NumericalOrbitPropagator.propagate_to (gravity-only force model, "
            "GravityConfiguration parallel=Never vs Always) divided by steps x RK4 stages. "
            "Includes integrator and ECI-ECEF frame-rotation overhead, estimated by "
            f"overhead_us_degree2; pooled median of {PASSES} passes x {REPEATS} interleaved runs per mode."
        ),
        "degrees": DEGREES,
        "serial_us": serial_us,
        "parallel_us": parallel_us,
        "serial_us_q25": stat(pooled_s, 0),
        "serial_us_q75": stat(pooled_s, 2),
        "parallel_us_q25": stat(pooled_p, 0),
        "parallel_us_q75": stat(pooled_p, 2),
        "overhead_us_degree2": serial_us[DEGREES.index(OVERHEAD_NMAX)],
        "auto_threshold_nmax": AUTO_THRESHOLD_NMAX,
        "measured_crossover_nmax": crossover(DEGREES, serial_us, parallel_us),
        "crossover_range_nmax": (
            [min(found), max(found)] if (found := [c for c in pass_crossovers if c is not None]) else None
        ),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
