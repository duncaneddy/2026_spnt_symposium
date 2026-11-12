# /// script
# requires-python = ">=3.12"
# dependencies = ["brahe @ git+https://github.com/duncaneddy/brahe@3e2ed7c1739b3f372c35c708702246bbee831183", "numpy"]
# ///
"""Broadcast-class TLE accuracy: SGP4 from a catalog GP versus an IGS orbit for one GPS satellite.

Takes the GPS satellite with the highest elevation at the talk epoch (from
Stanford, computed from the SP3 orbit exactly as in skyplot.py), propagates its
current public general perturbations (GP) element set with SGP4, and differences
the result against the IGS ultra-rapid precise orbit over a window centered on
the talk epoch, expressed in the radial / along-track / cross-track (RTN) frame
of the IGS orbit.

Data sources:
  - Orbit truth: IGS combined ultra-rapid orbit (IGS0OPSULT, 15 min samples)
    from the BKG mirror of the IGS archive. The newest issue covering the talk
    epoch is used; the second half of an issue is a prediction.
  - GP elements: CelesTrak "gps-ops" group, tried first with a short timeout;
    when it is unreachable, the on-orbit NAVSTAR objects from Space-Track
    (requires SPACETRACK_USER and SPACETRACK_PASS). The source used is recorded
    in the output as gp_source.

Frames and time:
  - SP3 epochs are GPS time and positions are Earth-fixed (IGS realization of
    ITRF). SGP4 output is TEME (true equator, mean equinox of date), which is not
    Earth-fixed and not GCRF; reading it as either gives errors of many
    kilometers to thousands of kilometers.
  - Both orbits are expressed in GCRF before differencing: the SP3 states by
    brahe's ITRF to GCRF transformation (IAU 2006/2000A with EOP), the SGP4
    states by TEME to GCRF. The RTN basis is built from the SP3 GCRF state, and
    the difference is SGP4 minus SP3.
  - The nominal window is 24 h centered on the talk epoch (UTC, 300 s steps),
    shortened symmetrically if the IGS product does not cover it; span_h in the
    output is the window actually used.

The PRN-to-NORAD mapping is found by matching the SP3 satellite's position at
the talk epoch to the nearest SGP4 position among the candidate GP objects; the
match must be unambiguous (nearest within 100 km, next nearest farther than
1000 km).

Raw downloads are cached in deck/data/raw/tle_vs_sp3/ and reused when present.

Run:
  uv run scripts/tle_vs_sp3.py [--out path.json]

Output (deck/data/tle_vs_sp3.json):
  {generated_utc, prn, norad, object_name, gp_source, tle_epoch_utc, product,
   span_h, t_h:[...], diff_rtn_km:{R,T,N}, diff_norm_km, rms_km, max_km}
  t_h is hours since the talk epoch; rms_km and max_km are over the 3D
  difference norm.
"""

import argparse
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

import brahe as bh
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "deck/data/tle_vs_sp3.json"
RAW_DIR = ROOT / "deck/data/raw/tle_vs_sp3"
GP_CACHE = RAW_DIR / "gps_gp.json"

EPOCH = bh.Epoch(2026, 11, 12, 19, 0, 0.0, 0.0, time_system=bh.UTC)
STANFORD = {"lat_deg": 37.4275, "lon_deg": -122.1697, "alt_m": 30.0}
NOMINAL_HALF_SPAN_S = 12 * 3600.0
STEP_S = 300.0
CELESTRAK_TIMEOUT_S = 15.0


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


def celestrak_gps() -> list[dict] | None:
    """CelesTrak gps-ops GP records, or None if CelesTrak does not answer in time."""
    tmp = RAW_DIR / "celestrak_gps_ops.json"
    query = bh.celestrak.CelestrakQuery.gp.group("gps-ops").format(bh.celestrak.CelestrakOutputFormat.JSON)
    client = bh.celestrak.CelestrakClient(max_retries=0)
    worker = threading.Thread(target=lambda: client.download(query, str(tmp)), daemon=True)
    worker.start()
    worker.join(CELESTRAK_TIMEOUT_S)
    if worker.is_alive() or not tmp.exists():
        return None
    try:
        return json.loads(tmp.read_text())
    except json.JSONDecodeError:
        return None
    finally:
        tmp.unlink(missing_ok=True)


def spacetrack_gps() -> list[dict]:
    """Space-Track GP records for all on-orbit NAVSTAR objects."""
    client = bh.SpaceTrackClient(os.environ["SPACETRACK_USER"], os.environ["SPACETRACK_PASS"])
    query = (
        bh.SpaceTrackQuery(bh.RequestClass.GP)
        .filter("OBJECT_NAME", "~~NAVSTAR")
        .filter("DECAY_DATE", "null-val")
        .order_by("NORAD_CAT_ID", bh.SortOrder.ASC)
    )
    return json.loads(client.query_raw(query))


def gps_gp_records() -> tuple[str, list[dict]]:
    """(source, records) for the GPS constellation, cached in RAW_DIR."""
    if not GP_CACHE.exists():
        records = celestrak_gps()
        source = "celestrak"
        if not records:
            records, source = spacetrack_gps(), "spacetrack"
        GP_CACHE.write_text(json.dumps({"source": source, "records": records}))
    cached = json.loads(GP_CACHE.read_text())
    return cached["source"], cached["records"]


def tle_lines(rec: dict) -> tuple[str, str]:
    """TLE lines of a GP record with blank-padded catalog numbers zero-padded."""
    return tuple(line[:2] + line[2:7].replace(" ", "0") + line[7:] for line in (rec["TLE_LINE1"], rec["TLE_LINE2"]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    out = parser.parse_args().out

    bh.initialize_eop()
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    client = bh.IGSProductsClient(bh.IGSProductSource.BKG)
    product = newest_product_covering(client, EPOCH)
    sp3 = bh.SP3.from_file(str(fetch_sp3(product, client)))

    # Highest-elevation GPS satellite at the talk epoch (SP3 ITRF -> local ENZ).
    site = np.array([STANFORD["lon_deg"], STANFORD["lat_deg"], STANFORD["alt_m"]])
    site_ecef = bh.position_geodetic_to_ecef(site, bh.AngleFormat.DEGREES)

    def elevation_deg(sat):
        enz = bh.relative_position_ecef_to_enz(
            site_ecef, sat.state_ecef(EPOCH)[:3], bh.EllipsoidalConversionType.GEODETIC
        )
        return bh.position_enz_to_azel(enz, bh.AngleFormat.DEGREES)[1]

    gps_sats = [s for s in sp3.satellites() if s.get_name().startswith("G")]
    sat = max(gps_sats, key=elevation_deg)
    prn = int(sat.get_name()[1:])

    # Identify the catalog object: nearest SGP4 position (GCRF) to the SP3 position at the epoch.
    gp_source, records = gps_gp_records()
    sat_gcrf_epoch = sat.state_gcrf(EPOCH)[:3]
    candidates = []
    for rec in records:
        propagator = bh.SGPPropagator.from_tle(*tle_lines(rec), 60.0)
        dist_km = np.linalg.norm(propagator.state_gcrf(EPOCH)[:3] - sat_gcrf_epoch) / 1e3
        candidates.append((dist_km, rec, propagator))
    candidates.sort(key=lambda c: c[0])
    (best_km, rec, sgp), (next_km, _, _) = candidates[0], candidates[1]
    assert best_km < 100.0 and next_km > 1000.0, f"ambiguous PRN match: {best_km:.1f} km vs {next_km:.1f} km"
    norad = int(rec["NORAD_CAT_ID"])

    # Window centered on the epoch, shortened symmetrically to the product coverage.
    half_s = min(NOMINAL_HALF_SPAN_S, EPOCH - sp3.start_epoch, sp3.end_epoch - EPOCH)
    half_s = np.floor(half_s / STEP_S) * STEP_S
    t_s = np.arange(-half_s, half_s + 1.0, STEP_S)
    epochs = [EPOCH + float(t) for t in t_s]

    # Core computation: both orbits in GCRF, SGP4 minus SP3 in the SP3 orbit's RTN frame.
    x_sp3 = np.array(sat.states_gcrf(epochs))
    x_sgp4 = np.array(sgp.states_gcrf(epochs))
    d_rtn_km = bh.state_eci_to_rtn(x_sp3, x_sgp4)[:, :3] / 1e3
    norm_km = np.linalg.norm(d_rtn_km, axis=1)
    rms_km = float(np.sqrt(np.mean(norm_km**2)))
    max_km = float(norm_km.max())

    assert 0.05 < rms_km < 20.0, f"rms {rms_km:.3f} km"
    assert max_km >= rms_km, f"max {max_km:.3f} km < rms {rms_km:.3f} km"

    result = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "prn": prn,
        "norad": norad,
        "object_name": rec["OBJECT_NAME"],
        "gp_source": gp_source,
        "tle_epoch_utc": sgp.epoch.isostring(),
        "product": product.name,
        "span_h": float(2 * half_s / 3600.0),
        "t_h": np.round(t_s / 3600.0, 4).tolist(),
        "diff_rtn_km": {k: np.round(d_rtn_km[:, i], 4).tolist() for i, k in enumerate("RTN")},
        "diff_norm_km": np.round(norm_km, 4).tolist(),
        "rms_km": round(rms_km, 4),
        "max_km": round(max_km, 4),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, separators=(",", ":")))

    print(f"product {product.name}; GP source {gp_source}")
    print(f"G{prn:02d} = NORAD {norad} ({rec['OBJECT_NAME']}), PRN match {best_km:.2f} km (next {next_km:.0f} km)")
    print(f"TLE epoch {sgp.epoch.isostring()}; window {result['span_h']:.1f} h, {len(t_s)} samples")
    print(f"RMS {rms_km:.3f} km, max {max_km:.3f} km")
    print(f"mean R/T/N {d_rtn_km.mean(axis=0).round(3)} km; peak |R|/|T|/|N| {np.abs(d_rtn_km).max(axis=0).round(3)} km")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
