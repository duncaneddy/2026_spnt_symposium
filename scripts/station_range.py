# /// script
# requires-python = ">=3.12"
# dependencies = ["brahe @ git+https://github.com/duncaneddy/brahe@3e2ed7c1739b3f372c35c708702246bbee831183", "numpy"]
# ///
"""Station to GPS satellite range, and what a wrong time system label does to it.

Picks the GPS satellite with the highest elevation at the reference instant from a
Stanford campus station, then computes the station to satellite range over the
visible pass containing that epoch at 30 s spacing in two ways:

  - correct: the SP3 timestamp 2026-11-12 19:00:00 is built as a GPS time epoch
    (SP3 epochs are GPS time), and the pass is evaluated at offsets from it.
    This reference instant is 19:00:00 GPS time, 18 s before 19:00:00 UTC; it
    is used for the satellite choice, the pass origin and the range budget.
    It lies in the predicted half of the ultra-rapid product.
  - mistaken: the same calendar fields labeled UTC. Brahe converts the label to
    the absolute instant, which lies 18 s (GPS minus UTC) later, so the
    satellite is evaluated 18 s away from where it should be. The two code
    paths differ by a single token, the time system argument.

The pass starts and ends at 0 deg elevation of the correctly timed satellite.
t_h is hours since 19:00:00 GPS time. pos_err_km is the satellite
displacement between the two cases at t_h = 0 and max_range_err_km is the
largest |wrong - correct| range over the pass.

Range budget at the reference instant (2026-11-12 19:00:00 GPS time) taken as
the signal reception time, in meters, as signed contributions to the modeled
pseudorange P = rho + c (dt_r - dt_s) (positive means P is longer):
  - geometric: |satellite(t_r) - station(t_r)| in the Earth-fixed frame at t_r.
  - light_time: satellite position at the transmission time t_tx = t_r - tau
    (tau = range / c, solved by fixed-point iteration), still in Earth-fixed
    axes of t_tx, minus the geometric range. This is the satellite's own motion
    during signal transit.
  - earth_rotation: the Sagnac term. The transmission-time position is rotated
    about the Earth's spin axis by omega_E * tau into the Earth-fixed axes of
    t_r, accounting for the Earth turning under the signal; the term is the
    resulting range minus the unrotated one.
  - sat_clock: -c * dt_s, with dt_s the SP3 satellite clock offset at the
    transmission time t_tx (seconds, linearly interpolated between the file's
    samples). A satellite clock that
    reads ahead (dt_s > 0) shortens P, so the term is negative. The receiver
    clock term c dt_r is not modeled.
The first three terms add up to the full range, geometric + light_time +
earth_rotation. sat_clock is separate.

Data source:
  - IGS combined ultra-rapid orbit and clock product (IGS0OPSULT, 15 min
    samples) from the BKG mirror of the IGS archive, which needs no login. The
    newest issue whose span covers the epoch is selected.

Frames and time:
  - SP3 positions are Earth-fixed (IGS realization of ITRF), epochs are GPS
    time. Ranges use Euclidean distance in that frame; no atmosphere, antenna
    or relativistic clock effects are modeled.
  - GPS minus UTC is obtained from brahe's time system conversion.

Raw downloads are cached in deck/data/raw/station_range/ and reused when present.

Run:
  uv run scripts/station_range.py [--out path.json]

Output (deck/data/station_range.json):
  {generated_utc, product, prn, station, gps_minus_utc_s, t_h, range_km,
   range_wrong_km, range_err_km, pos_err_km, max_range_err_km,
   terms_m:{geometric, light_time, earth_rotation, sat_clock}}
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import brahe as bh
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "deck/data/station_range.json"
RAW_DIR = ROOT / "deck/data/raw/station_range"

STANFORD = {"name": "STANFORD", "lat_deg": 37.4275, "lon_deg": -122.1697, "alt_m": 30.0}
STEP_S = 30.0


def newest_product_covering(client: bh.IGSProductsClient, epoch: bh.Epoch) -> bh.IGSProduct:
    """Latest-starting IGS ultra-rapid SP3 product whose span contains the epoch."""
    products = client.list_products_between(
        epoch,
        epoch,
        center=bh.IGSAnalysisCenter.IGS,
        solution=bh.IGSSolutionType.ULTRA_RAPID,
        content=bh.IGSContentType.ORBIT,
        format=bh.IGSFileFormat.SP3,
    )
    covering = [p for p in products if 0.0 <= epoch - p.file_name.start_epoch <= p.file_name.span]
    if not covering:
        raise RuntimeError(f"no IGS ultra-rapid product covers {epoch}")
    return min(covering, key=lambda p: epoch - p.file_name.start_epoch)


def fetch_sp3(product: bh.IGSProduct, client: bh.IGSProductsClient) -> Path:
    """Product file in RAW_DIR as published, downloaded only when absent."""
    path = RAW_DIR / product.name
    if not path.exists():
        client.save(product, str(RAW_DIR))
    return path


def rotate_about_z(vec: np.ndarray, angle_rad: float) -> np.ndarray:
    """Coordinates of a fixed vector in axes rotated by angle_rad about +z."""
    c, s = np.cos(angle_rad), np.sin(angle_rad)
    return np.array([c * vec[0] + s * vec[1], -s * vec[0] + c * vec[1], vec[2]])


def clock_offset_s(sat, epoch: bh.Epoch) -> float:
    """SP3 clock offset in seconds, linearly interpolated between samples."""
    t = np.array([e - epoch for e in sat.epochs()])
    clocks = sat.clocks()
    near = np.argsort(np.abs(t))[:2]
    assert np.all(np.isfinite(clocks[near])) and np.all(np.abs(clocks[near]) < 0.1), "invalid SP3 clock"
    return float(np.interp(0.0, t, clocks))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    out = parser.parse_args().out

    # Same calendar fields, two time system labels: the only difference is the last argument.
    correct = bh.Epoch(2026, 11, 12, 19, 0, 0.0, 0.0, time_system=bh.GPS)
    mistaken = bh.Epoch(2026, 11, 12, 19, 0, 0.0, 0.0, time_system=bh.UTC)

    client = bh.IGSProductsClient(bh.IGSProductSource.BKG)
    product = newest_product_covering(client, correct)
    sp3 = bh.SP3.from_file(str(fetch_sp3(product, client)))

    site = np.array([STANFORD["lon_deg"], STANFORD["lat_deg"], STANFORD["alt_m"]])
    site_ecef = bh.position_geodetic_to_ecef(site, bh.AngleFormat.DEGREES)

    def elevation_deg(sat, t):
        enz = bh.relative_position_ecef_to_enz(
            site_ecef, sat.state_ecef(t)[:3], bh.EllipsoidalConversionType.GEODETIC
        )
        return bh.position_enz_to_azel(enz, bh.AngleFormat.DEGREES)[1]

    def range_m(sat, t):
        return float(np.linalg.norm(sat.state_ecef(t)[:3] - site_ecef))

    gps_sats = [s for s in sp3.satellites() if s.get_name().startswith("G")]
    sat = max(gps_sats, key=lambda s: elevation_deg(s, correct))
    prn = int(sat.get_name()[1:])

    gps_minus_utc_s = bh.time_system_offset_for_mjd(mistaken.mjd(), bh.UTC, bh.GPS)
    pos_err_m = float(np.linalg.norm(sat.state_ecef(mistaken)[:3] - sat.state_ecef(correct)[:3]))

    # Visible pass containing the epoch: walk outward from it until the satellite sets.
    offsets = [0.0]
    for direction in (-1.0, 1.0):
        k = 1
        while elevation_deg(sat, correct + direction * k * STEP_S) >= 0.0:
            offsets.append(direction * k * STEP_S)
            k += 1
    offsets.sort()

    range_km = np.array([range_m(sat, correct + dt) for dt in offsets]) / 1e3
    range_wrong_km = np.array([range_m(sat, mistaken + dt) for dt in offsets]) / 1e3
    range_err_km = range_wrong_km - range_km

    # Range budget at reception time, Earth-fixed frame.
    geometric = range_m(sat, correct)
    tau = geometric / bh.C_LIGHT
    for _ in range(10):
        r_tx = sat.state_ecef(correct - tau)[:3]
        rotated = rotate_about_z(r_tx, bh.OMEGA_EARTH * tau)
        tau = np.linalg.norm(rotated - site_ecef) / bh.C_LIGHT
    unrotated_range = float(np.linalg.norm(r_tx - site_ecef))
    full_range = float(np.linalg.norm(rotated - site_ecef))
    terms_m = {
        "geometric": geometric,
        "light_time": unrotated_range - geometric,
        "earth_rotation": full_range - unrotated_range,
        "sat_clock": -clock_offset_s(sat, correct - tau) * bh.C_LIGHT,
    }

    max_range_err_km = float(np.abs(range_err_km).max())

    assert gps_minus_utc_s == 18, f"GPS - UTC = {gps_minus_utc_s} s"
    assert abs(geometric / 1e3 - range_km[offsets.index(0.0)]) < 1e-3, "budget and pass ranges disagree at t_h = 0"
    assert np.all((range_km > 20_000.0) & (range_km < 26_000.0)), "range out of range"
    assert np.all((range_wrong_km > 20_000.0) & (range_wrong_km < 26_000.0)), "wrong range out of range"
    assert 50.0 < pos_err_m / 1e3 < 80.0, f"position error {pos_err_m / 1e3} km"
    assert max_range_err_km < pos_err_m / 1e3, "range error exceeds position error"
    assert abs(terms_m["earth_rotation"]) < 50.0, f"Sagnac {terms_m['earth_rotation']} m"

    result = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "product": product.name,
        "prn": prn,
        "station": STANFORD,
        "gps_minus_utc_s": int(gps_minus_utc_s),
        "t_h": [round(dt / 3600.0, 6) for dt in offsets],
        "range_km": [round(float(r), 4) for r in range_km],
        "range_wrong_km": [round(float(r), 4) for r in range_wrong_km],
        "range_err_km": [round(float(r), 5) for r in range_err_km],
        "pos_err_km": pos_err_m / 1e3,
        "max_range_err_km": max_range_err_km,
        "terms_m": terms_m,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, separators=(",", ":")))

    print(f"product {product.name}, G{prn:02d} at {elevation_deg(sat, correct):.1f} deg elevation")
    print(f"pass {offsets[0] / 3600:.2f} to {offsets[-1] / 3600:.2f} h, {len(offsets)} samples")
    print(f"GPS - UTC {gps_minus_utc_s:.0f} s, satellite displacement {pos_err_m / 1e3:.2f} km")
    print(f"range {range_km.min():.0f} to {range_km.max():.0f} km, max range error {max_range_err_km:.2f} km")
    print("terms (m): " + ", ".join(f"{k} {v:.3f}" for k, v in terms_m.items()))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
