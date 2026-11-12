# /// script
# requires-python = ">=3.12"
# dependencies = ["brahe @ git+https://github.com/duncaneddy/brahe@3e2ed7c1739b3f372c35c708702246bbee831183", "numpy"]
# ///
"""GPS constellation motion over one orbital period, in an inertial frame.

Loads the newest IGS ultra-rapid SP3 orbit product (BKG mirror, no login) that
covers the talk epoch and converts every GPS satellite's position to GCRF at
300 s spacing. The span is the multiple of the sampling step nearest one
orbital period, so a looped replay closes nearly seamlessly. The window starts
at the talk epoch when the product's coverage extends a full span beyond it;
otherwise it starts earlier, on a 300 s boundary, so that it ends at the end
of coverage and still contains the talk epoch. Positions are never
extrapolated beyond the product. The window lies in the predicted half of
the IGS ultra-rapid product.

Frames and time:
  - SP3 epochs are GPS time and positions are Earth-fixed (IGS realization of
    ITRF). Positions are rotated to GCRF with Earth-orientation data, so the
    constellation is shown as seen from a non-rotating frame.
  - The epoch is 2026-11-12 19:00:00 UTC.
  - The orbital period is that of the mean semi-major axis of the
    constellation, from the osculating GCRF state at the epoch.
  - Orbital planes are found by clustering the right ascension of the
    ascending node, computed from the GCRF angular momentum vector, into six
    groups separated by the largest gaps in RAAN.

Raw downloads are cached in deck/data/raw/gps_constellation/ and reused when present.

Run:
  uv run scripts/gps_constellation.py [--out path.json]

Output (deck/data/gps_constellation.json):
  {generated_utc, epoch_utc (window start), talk_epoch_utc, talk_index, product, frame, step_s, period_s, prns,
   xyz_km: [time][satellite][x, y, z] (0.1 km), planes}
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import brahe as bh
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "deck/data/gps_constellation.json"
RAW_DIR = ROOT / "deck/data/raw/gps_constellation"

EPOCH = bh.Epoch(2026, 11, 12, 19, 0, 0.0, 0.0, time_system=bh.UTC)
STEP_S = 300
SP3_SAMPLE_S = 900
N_PLANES = 6


def covers(name: bh.IGSProductFileName, epoch: bh.Epoch) -> bool:
    return 0.0 <= epoch - name.start_epoch <= name.span


def orbit_file(epoch: bh.Epoch) -> Path:
    """Newest ultra-rapid SP3 file in RAW_DIR covering the epoch, downloaded only when absent."""
    try:
        client = bh.IGSProductsClient(bh.IGSProductSource.BKG)
        products = client.list_products_between(
            epoch,
            epoch,
            center=bh.IGSAnalysisCenter.IGS,
            solution=bh.IGSSolutionType.ULTRA_RAPID,
            content=bh.IGSContentType.ORBIT,
            format=bh.IGSFileFormat.SP3,
        )
        covering = [p for p in products if covers(p.file_name, epoch)]
        if not covering:
            raise RuntimeError(f"no IGS ultra-rapid product covers {epoch}")
        product = min(covering, key=lambda p: epoch - p.file_name.start_epoch)
        path = RAW_DIR / product.name
        if not path.exists():
            client.save(product, str(RAW_DIR))
        return path
    except bh.BraheError:
        cached = [p for p in RAW_DIR.glob("IGS0OPSULT_*.SP3*") if covers(bh.IGSProductFileName.parse(p.name), epoch)]
        if not cached:
            raise
        return min(cached, key=lambda p: epoch - bh.IGSProductFileName.parse(p.name).start_epoch)


def window_offset_s(coverage_end_s: float, span_s: int) -> int:
    """Window start relative to the talk epoch: zero if the window fits, else the latest 300 s multiple that fits."""
    return min(0, int(np.floor((coverage_end_s - span_s) / STEP_S)) * STEP_S)


def raan_deg(state: np.ndarray) -> float:
    """Right ascension of the ascending node in degrees from the angular momentum vector."""
    h = np.cross(state[:3], state[3:6])
    return float(np.degrees(np.arctan2(h[0], -h[1])) % 360.0)


def cluster_planes(raan: np.ndarray, n_planes: int) -> np.ndarray:
    """Plane index 0..n-1 (ascending mean RAAN) from cutting the circular RAAN list at its n largest gaps."""
    order = np.argsort(raan)
    gaps = np.diff(np.append(raan[order], raan[order][0] + 360.0))
    cuts = np.sort(np.argsort(gaps)[-n_planes:])
    groups = np.zeros(len(raan), dtype=int)
    for k, (lo, hi) in enumerate(zip(cuts, np.roll(cuts, -1))):
        idx = order[lo + 1 : hi + 1] if hi > lo else np.concatenate([order[lo + 1 :], order[: hi + 1]])
        groups[idx] = k
    mean_raan = np.array([np.angle(np.exp(1j * np.radians(raan[groups == k])).mean(), deg=True) % 360.0 for k in range(n_planes)])
    rank = np.argsort(np.argsort(mean_raan))
    return rank[groups]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    out = parser.parse_args().out

    bh.initialize_eop()
    path = orbit_file(EPOCH)

    sp3 = bh.SP3.from_file(str(path))
    gps = sorted((s for s in sp3.satellites() if s.get_name().startswith("G")), key=lambda s: s.get_name())

    x0 = np.array([s.state_gcrf(EPOCH) for s in gps])
    a_mean = np.mean([bh.state_eci_to_koe(x, bh.AngleFormat.DEGREES)[0] for x in x0])
    period_s = bh.orbital_period(a_mean)
    n_steps = round(period_s / STEP_S)
    name = bh.IGSProductFileName.parse(path.name)
    start = EPOCH + window_offset_s(name.start_epoch + name.span - SP3_SAMPLE_S - EPOCH, n_steps * STEP_S)
    assert start - name.start_epoch >= 0.0, "product does not cover one period"
    epochs = [start + STEP_S * k for k in range(n_steps + 1)]
    talk_index = int(np.argmin([abs(e - EPOCH) for e in epochs]))
    xyz_km = np.stack([np.array(s.states_gcrf(epochs))[:, :3] for s in gps], axis=1) / 1e3

    raan = np.array([raan_deg(x) for x in x0])
    planes = cluster_planes(raan, N_PLANES)

    radius_km = np.linalg.norm(xyz_km, axis=2)
    closure_km = np.linalg.norm(xyz_km[-1] - xyz_km[0], axis=1)
    counts = np.bincount(planes, minlength=N_PLANES)
    spreads = [float(np.ptp(raan[planes == k])) for k in range(N_PLANES)]

    assert 24 <= len(gps) <= 34, f"{len(gps)} GPS satellites"
    assert np.all((25_500.0 <= radius_km) & (radius_km <= 27_700.0)), "satellite radius out of range"
    assert len(set(planes)) == N_PLANES and counts.min() >= 3, f"plane counts {counts}"
    assert max(spreads) < 25.0, f"plane RAAN spreads {spreads}"
    assert closure_km.max() < 2_500.0, f"first-to-last distance {closure_km.max():.0f} km"

    result = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "epoch_utc": start.isostring(),
        "talk_epoch_utc": EPOCH.isostring(),
        "talk_index": talk_index,
        "product": path.name,
        "frame": "GCRF",
        "step_s": STEP_S,
        "period_s": round(float(period_s), 1),
        "prns": [int(s.get_name()[1:]) for s in gps],
        "xyz_km": np.round(xyz_km, 1).tolist(),
        "planes": planes.tolist(),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, separators=(",", ":")))

    print(f"product {path.name}")
    print(f"window {start.isostring()} to {epochs[-1].isostring()}, talk epoch at sample {talk_index}")
    print(f"{len(gps)} GPS satellites, {len(epochs)} samples, period {period_s:.1f} s, a {a_mean / 1e3:.1f} km")
    print("satellites per plane:", counts.tolist(), "RAAN spreads (deg):", [round(s, 1) for s in spreads])
    print(f"max first-to-last closure {closure_km.max():.0f} km")
    print(f"wrote {out} ({out.stat().st_size / 1e3:.0f} KB)")


if __name__ == "__main__":
    main()
