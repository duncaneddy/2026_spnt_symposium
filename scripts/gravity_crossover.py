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
  - propagate_to() on a fresh propagator, median of REPEATS runs after one
    discarded warm-up run. Construction and model loading are not timed.
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
  {generated_utc, machine:{cpu, threads, load_avg_1min_start, load_avg_1min_end}, model, max_degree_available, kernel,
   integrator, steps, stages_per_step, method, degrees, serial_us, parallel_us,
   overhead_us_degree2, auto_threshold_nmax, measured_crossover_nmax}
  serial_us / parallel_us are microseconds per gravity evaluation.
  measured_crossover_nmax is the first degree from which parallel stays faster
  than serial through the end of the sweep, or null.
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

DEGREES = [2, 10, 20, 50, 90, 120, 150, 180, 210, 240, 300, 360]
OVERHEAD_NMAX = 2
AUTO_THRESHOLD_NMAX = 180
STEP_S = 10.0
STEPS = 200
STAGES_PER_STEP = 4
REPEATS = 21

EPOCH = bh.Epoch(2026, 11, 12, 19, 0, 0.0, 0.0, time_system=bh.UTC)
ORBIT = np.array([bh.R_EARTH + 550e3, 0.001, 53.0, 15.0, 30.0, 45.0])


def ensure_model() -> Path:
    if not MODEL_FILE.exists():
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(MODEL_URL, timeout=120) as resp:
            MODEL_FILE.write_bytes(resp.read())
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


def per_eval_us(model_type: bh.GravityModelType, degree: int, mode: bh.ParallelMode) -> float:
    propagation_time_s(model_type, degree, mode)
    times = [propagation_time_s(model_type, degree, mode) for _ in range(REPEATS)]
    return statistics.median(times) / (STEPS * STAGES_PER_STEP) * 1e6


def crossover(degrees: list[int], serial: list[float], parallel: list[float]) -> int | None:
    result = None
    for n, s, p in zip(reversed(degrees), reversed(serial), reversed(parallel)):
        if p < s:
            result = n
        else:
            break
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    bh.initialize_eop()
    model_type = bh.GravityModelType.from_file(str(ensure_model()))

    load_start = os.getloadavg()[0]
    serial_us, parallel_us = [], []
    for n in DEGREES:
        serial_us.append(per_eval_us(model_type, n, bh.ParallelMode.Never))
        parallel_us.append(per_eval_us(model_type, n, bh.ParallelMode.Always))
        print(f"n={n:4d}  serial {serial_us[-1]:9.2f} us  parallel {parallel_us[-1]:9.2f} us")

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
        "max_degree_available": MAX_DEGREE_AVAILABLE,
        "kernel": "Clenshaw",
        "integrator": f"RK4 fixed step {STEP_S:g} s",
        "steps": STEPS,
        "stages_per_step": STAGES_PER_STEP,
        "method": (
            "Wall time of NumericalOrbitPropagator.propagate_to (gravity-only force model, "
            "GravityConfiguration parallel=Never vs Always) divided by steps x RK4 stages. "
            "Includes integrator and ECI-ECEF frame-rotation overhead, estimated by "
            f"overhead_us_degree2; median of {REPEATS} runs after one warm-up run."
        ),
        "degrees": DEGREES,
        "serial_us": serial_us,
        "parallel_us": parallel_us,
        "overhead_us_degree2": serial_us[DEGREES.index(OVERHEAD_NMAX)],
        "auto_threshold_nmax": AUTO_THRESHOLD_NMAX,
        "measured_crossover_nmax": crossover(DEGREES, serial_us, parallel_us),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
