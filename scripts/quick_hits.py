# /// script
# requires-python = ">=3.12"
# dependencies = ["brahe @ git+https://github.com/duncaneddy/brahe@3e2ed7c1739b3f372c35c708702246bbee831183", "numpy"]
# ///
"""Three short brahe examples: GPS ground tracks, force-model choice, and reference frames.

Each block is one function of a few lines of brahe.

(a) tle_ground_tracks: 12 h ground tracks at 120 s for six GPS satellites, one per orbital
    plane, from the GP element sets of the CelesTrak `gps-ops` group propagated with SGP4.
(b) propagate_sso: a 500 km sun-synchronous orbit for 3 days at 300 s, once with two-body
    dynamics and once with brahe's default force model (20x20 EGM2008 gravity, NRLMSISE-00
    drag, solar radiation pressure, Sun and Moon third-body), recording geodetic altitude.
(c) frames: one GPS orbit from an IGS ultra-rapid SP3 file over 24 h at 300 s, as GCRF
    (inertial) and ITRF (Earth-fixed) position vectors.

Data sources:
  - GP elements: CelesTrak `gps-ops`. CelesTrak is tried first; if it is unreachable the
    NAVSTAR element sets are queried from Space-Track (needs SPACETRACK_USER and
    SPACETRACK_PASS in the environment). Space-Track has no operational flag, so the fallback
    assigns each SP3 GPS satellite (the satellites the IGS tracks) the element set whose
    SGP4 position at the talk epoch is nearest, requires the assignment to be one-to-one and
    within 50 km, and keeps those element sets. Which source was used is recorded in the
    output.
  - SP3: IGS combined ultra-rapid orbit (IGS0OPSULT, 15 min samples) from the BKG mirror.

Frames and time:
  - Epochs are UTC; SP3 epochs are GPS time and brahe compares instants across time systems.
  - SGP4 output is TEME; brahe rotates it to ITRF for ground tracks. Geodetic longitude and
    latitude are on the WGS84 ellipsoid. Ground tracks start at the talk epoch.
  - SP3 positions are ITRF (IGS realization); GCRF positions use brahe's IAU 2006/2000A
    transformation with Earth orientation parameters.
  - Block (c) gives one state in two frames, so the GCRF and ITRF radii agree to rounding.
    Block (b) altitudes are height above the WGS84 ellipsoid, which varies by about 21 km
    around an orbit; dr_km and dr_drag_km are GCRF position differences between runs.

Raw downloads are cached in deck/data/raw/quick_hits/ and reused when present.

Run:
  uv run scripts/quick_hits.py [--out path.json]

Output (deck/data/quick_hits.json):
  {generated_utc,
   tle:{group, source, n, epoch_utc, inc_range_deg:[min, max], match_max_residual_km|null,
        tracks:[{name, norad, inc_deg, lonlat_deg:[[lon, lat], ...]}]},
   propagate:{object, inc_deg, t_h:[...], alt_twobody_km:[...], alt_full_km:[...],
              dr_km:[...], dr_drag_km:[...], force_model},
   frames:{prn, t_h:[...], eci_xyz_km:[[x, y, z], ...], ecef_xyz_km:[[x, y, z], ...]}}
  dr_km is |r_full - r_twobody| and dr_drag_km is |r_full - r_full_without_drag|, both in GCRF.
  tle.epoch_utc is the first ground-track sample; the t_h arrays are hours after the
  propagation or frames start epoch.
"""

import argparse
import json
import os
import socket
from datetime import datetime, timezone
from pathlib import Path

import brahe as bh
import numpy as np
from brahe.spacetrack import operators as op

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "deck/data/quick_hits.json"
RAW_DIR = ROOT / "deck/data/raw/quick_hits"
GP_CACHE = RAW_DIR / "gps-ops.json"
GP_SOURCE_CACHE = RAW_DIR / "gps-ops.source"

EPOCH = bh.Epoch(2026, 11, 12, 19, 0, 0.0, 0.0, time_system=bh.UTC)

N_PLANES = 6
TRACK_SPAN_S, TRACK_STEP_S = 12 * 3600, 120

SSO_ALT_KM = 500.0
SSO_SPAN_S, SSO_STEP_S = 3 * 86400, 300
SSO_PARAMS = np.array([100.0, 1.0, 2.2, 1.0, 1.3])  # mass kg, drag area m^2, Cd, SRP area m^2, Cr

FRAMES_PRN = 1
MATCH_KM = 50.0
FRAMES_SPAN_S, FRAMES_STEP_S = 86400, 300


def operational(records: list[dict], sp3: bh.SP3) -> tuple[list[dict], float]:
    """Element sets matched one-to-one to the SP3 GPS satellites by SGP4 position at EPOCH (ITRF),
    and the largest matched distance in km."""
    gps_ecef = np.array([s.state_ecef(EPOCH)[:3] for s in sp3.satellites() if s.get_name().startswith("G")])
    sgp_ecef = np.array(
        [np.array(bh.GPRecord.from_json(json.dumps(r)).to_sgp_propagator(60.0).state_itrf(EPOCH))[:3] for r in records]
    )
    dist_km = np.linalg.norm(gps_ecef[:, None, :] - sgp_ecef[None, :, :], axis=2) / 1e3
    nearest = dist_km.argmin(axis=1)
    assert len(set(nearest)) == len(nearest), "two SP3 satellites matched the same element set"
    residual_km = float(dist_km[np.arange(len(nearest)), nearest].max())
    assert residual_km < MATCH_KM, f"SP3 to GP match residual {residual_km:.1f} km"
    return [records[i] for i in sorted(nearest)], residual_km


def fetch_gp_records(sp3: bh.SP3) -> tuple[list[dict], dict]:
    """GPS GP records and their provenance ({source, match_max_residual_km}), from the cache or
    CelesTrak, else Space-Track."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if GP_CACHE.exists() and GP_SOURCE_CACHE.exists():
        return json.loads(GP_CACHE.read_text()), json.loads(GP_SOURCE_CACHE.read_text())

    try:
        socket.create_connection(("celestrak.org", 443), timeout=5).close()
        query = bh.celestrak.CelestrakQuery.gp.group("gps-ops").format(bh.celestrak.CelestrakOutputFormat.JSON)
        bh.celestrak.CelestrakClient(max_retries=0).download(query, str(GP_CACHE))
        provenance = {"source": "celestrak", "match_max_residual_km": None}
    except (OSError, bh.BraheError) as err:
        print(f"CelesTrak unreachable ({err}); using Space-Track")
        client = bh.SpaceTrackClient(os.environ["SPACETRACK_USER"], os.environ["SPACETRACK_PASS"])
        query = (
            bh.SpaceTrackQuery(bh.RequestClass.GP)
            .filter("OBJECT_NAME", op.like("NAVSTAR"))
            .filter("DECAY_DATE", op.null_val())
            .filter("EPOCH", op.greater_than(op.now_offset(-30)))
            .order_by("NORAD_CAT_ID", bh.SortOrder.ASC)
        )
        records, residual_km = operational(json.loads(client.query_raw(query)), sp3)
        GP_CACHE.write_text(json.dumps(records, indent=1))
        provenance = {"source": "space-track", "match_max_residual_km": round(residual_km, 3)}
    GP_SOURCE_CACHE.write_text(json.dumps(provenance))
    return json.loads(GP_CACHE.read_text()), provenance


def one_per_plane(records: list[dict], n_planes: int) -> list[dict]:
    """Group the satellites into n_planes equally spaced RAAN planes, phased to fit the
    constellation's RAANs best, and take from each plane the satellite whose RAAN is nearest
    the plane's median RAAN."""
    raan = np.array([float(r["RA_OF_ASC_NODE"]) for r in records])
    width = 360.0 / n_planes

    def misfit(phase: float) -> float:
        d = (raan - phase + width / 2) % width - width / 2
        return float(np.sum(d**2))

    phase = min(np.arange(0.0, width, 0.5), key=misfit)
    plane = np.round((raan - phase) / width).astype(int) % n_planes
    offset = (raan - phase + width / 2) % width - width / 2
    chosen = []
    for k in range(n_planes):
        members = np.flatnonzero(plane == k)
        chosen.append(records[int(members[np.argmin(np.abs(offset[members] - np.median(offset[members])))])])
    return chosen


def tle_ground_tracks(records: list[dict]) -> list[dict]:
    """Ground track of each GP record: SGP4 propagated, TEME to ITRF, then geodetic lon/lat."""
    epochs = [EPOCH + t for t in range(0, TRACK_SPAN_S + 1, TRACK_STEP_S)]
    tracks = []
    for rec in records:
        sat = bh.GPRecord.from_json(json.dumps(rec)).to_sgp_propagator(TRACK_STEP_S)
        r_itrf = np.array(sat.states_itrf(epochs))[:, :3]
        lonlat = [bh.position_ecef_to_geodetic(r, bh.AngleFormat.DEGREES)[:2] for r in r_itrf]
        tracks.append(
            {
                "name": rec["OBJECT_NAME"],
                "norad": int(rec["NORAD_CAT_ID"]),
                "inc_deg": round(float(rec["INCLINATION"]), 3),
                "lonlat_deg": [[round(float(lon), 3), round(float(lat), 3)] for lon, lat in lonlat],
            }
        )
    return tracks


def propagate(x0: np.ndarray, force: bh.ForceModelConfig, epochs: list[bh.Epoch]) -> bh.NumericalOrbitPropagator:
    """Numerically propagate x0 (GCRF, at EPOCH) under a force model to the last epoch."""
    config = bh.NumericalPropagationConfig.with_method(bh.IntegrationMethod.RKF78).with_abs_tol(1e-6).with_rel_tol(1e-12)
    prop = bh.NumericalOrbitPropagator(EPOCH, x0, config, force, SSO_PARAMS)
    prop.propagate_to(epochs[-1])
    return prop


def propagate_sso() -> dict:
    """A 500 km sun-synchronous orbit under two-body, full, and full-without-drag force models:
    geodetic altitude for the first two, and the GCRF position differences that isolate the
    effect of the full model and of drag alone."""
    a = bh.R_EARTH + SSO_ALT_KM * 1e3
    inc = bh.sun_synchronous_inclination(a, 0.0, angle_format=bh.AngleFormat.DEGREES)
    x0 = bh.state_koe_to_eci(np.array([a, 0.0, inc, 0.0, 0.0, 0.0]), bh.AngleFormat.DEGREES)
    epochs = [EPOCH + t for t in range(0, SSO_SPAN_S + 1, SSO_STEP_S)]

    no_drag = bh.ForceModelConfig.default()
    no_drag.drag = None
    runs = {
        "twobody": propagate(x0, bh.ForceModelConfig.two_body(), epochs),
        "full": propagate(x0, bh.ForceModelConfig.default(), epochs),
        "no_drag": propagate(x0, no_drag, epochs),
    }
    r_gcrf = {k: np.array(p.states_gcrf(epochs))[:, :3] for k, p in runs.items()}

    def altitude_km(prop: bh.NumericalOrbitPropagator) -> list[float]:
        r_itrf = np.array(prop.states_itrf(epochs))[:, :3]
        return [float(bh.position_ecef_to_geodetic(r, bh.AngleFormat.DEGREES)[2]) / 1e3 for r in r_itrf]

    return {
        "inc_deg": inc,
        "t_h": [(e - EPOCH) / 3600.0 for e in epochs],
        "alt_twobody_km": altitude_km(runs["twobody"]),
        "alt_full_km": altitude_km(runs["full"]),
        "dr_km": np.linalg.norm(r_gcrf["full"] - r_gcrf["twobody"], axis=1) / 1e3,
        "dr_drag_km": np.linalg.norm(r_gcrf["full"] - r_gcrf["no_drag"], axis=1) / 1e3,
    }


def frames(sat: bh.SP3Satellite) -> dict:
    """GPS positions over 24 h before the talk epoch, in GCRF (inertial) and ITRF (Earth-fixed)."""
    t0 = EPOCH - FRAMES_SPAN_S
    epochs = [t0 + t for t in range(0, FRAMES_SPAN_S + 1, FRAMES_STEP_S)]
    return {
        "t_h": [(e - t0) / 3600.0 for e in epochs],
        "eci_xyz_km": np.array(sat.states_gcrf(epochs))[:, :3] / 1e3,
        "ecef_xyz_km": np.array(sat.states_itrf(epochs))[:, :3] / 1e3,
    }


def newest_product_covering(client: bh.IGSProductsClient, epoch: bh.Epoch) -> bh.IGSProduct:
    """Latest-starting IGS ultra-rapid SP3 product whose span contains the epoch."""
    products = client.list_products_between(
        epoch - FRAMES_SPAN_S,
        epoch,
        center=bh.IGSAnalysisCenter.IGS,
        solution=bh.IGSSolutionType.ULTRA_RAPID,
        content=bh.IGSContentType.ORBIT,
        format=bh.IGSFileFormat.SP3,
    )
    covering = [
        p
        for p in products
        if 0.0 <= epoch - FRAMES_SPAN_S - p.file_name.start_epoch and epoch - p.file_name.start_epoch <= p.file_name.span
    ]
    if not covering:
        raise RuntimeError(f"no IGS ultra-rapid product covers {epoch - FRAMES_SPAN_S} to {epoch}")
    return min(covering, key=lambda p: epoch - p.file_name.start_epoch)


def fetch_sp3() -> tuple[bh.SP3, str]:
    """SP3 file covering the frames window: a cached one when it covers it, else downloaded."""
    t0 = EPOCH - FRAMES_SPAN_S
    for path in sorted(RAW_DIR.glob("IGS0OPSULT_*.SP3.gz")):
        sp3 = bh.SP3.from_file(str(path))
        if sp3.start_epoch <= t0 and sp3.end_epoch >= EPOCH:
            return sp3, path.name
    client = bh.IGSProductsClient(bh.IGSProductSource.BKG)
    product = newest_product_covering(client, EPOCH)
    client.save(product, str(RAW_DIR))
    return bh.SP3.from_file(str(RAW_DIR / product.name)), product.name


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    out = parser.parse_args().out

    bh.initialize_eop()
    bh.initialize_sw()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    sp3, sp3_name = fetch_sp3()

    records, provenance = fetch_gp_records(sp3)
    tracks = tle_ground_tracks(one_per_plane(records, N_PLANES))
    inc_range = [min(float(r["INCLINATION"]) for r in records), max(float(r["INCLINATION"]) for r in records)]
    sso = propagate_sso()

    sat = next(s for s in sp3.satellites() if s.get_name() == f"G{FRAMES_PRN:02d}")
    fr = frames(sat)

    radius_diff_m = 1e3 * np.abs(np.linalg.norm(fr["eci_xyz_km"], axis=1) - np.linalg.norm(fr["ecef_xyz_km"], axis=1))
    max_lat = max(abs(lat) for t in tracks for _, lat in t["lonlat_deg"])

    assert len(records) >= 24, f"{len(records)} GPS element sets"
    assert len(tracks) == N_PLANES, f"{len(tracks)} ground tracks"
    max_inc = max(t["inc_deg"] for t in tracks)
    assert max_lat <= max_inc + 0.3, f"ground track latitude {max_lat:.2f} deg exceeds inclination {max_inc:.2f} deg + 0.3"
    drag_day_max = [sso["dr_drag_km"][i : i + 288].max() for i in range(0, len(sso["dr_drag_km"]) - 1, 288)]
    assert sso["dr_km"][-1] > 100.0, f"two-body differs from full by only {sso['dr_km'][-1]:.1f} km"
    assert all(x <= y for x, y in zip(drag_day_max, drag_day_max[1:])), f"drag effect envelope {drag_day_max}"
    assert 0.0 < sso["dr_drag_km"][-1] < sso["dr_km"][-1], "drag effect not between zero and the full-model difference"
    assert radius_diff_m.max() <= 1.0, f"ECI and ECEF radii differ by {radius_diff_m.max():.3f} m"

    result = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tle": {
            "group": "gps-ops",
            "source": provenance["source"],
            "match_max_residual_km": provenance["match_max_residual_km"],
            "n": len(records),
            "inc_range_deg": [round(v, 3) for v in inc_range],
            "epoch_utc": EPOCH.isostring(),
            "tracks": tracks,
        },
        "propagate": {
            "object": f"{SSO_ALT_KM:.0f} km sun-synchronous orbit",
            "inc_deg": round(sso["inc_deg"], 3),
            "t_h": np.round(sso["t_h"], 4).tolist(),
            "alt_twobody_km": np.round(sso["alt_twobody_km"], 3).tolist(),
            "alt_full_km": np.round(sso["alt_full_km"], 3).tolist(),
            "dr_km": np.round(sso["dr_km"], 4).tolist(),
            "dr_drag_km": np.round(sso["dr_drag_km"], 5).tolist(),
            "force_model": "default: 20x20 EGM2008, NRLMSISE-00 drag, SRP with conical eclipse, Sun and Moon; "
            "m=100 kg, A=1 m^2, Cd=2.2, Cr=1.3; RKF78",
        },
        "frames": {
            "prn": FRAMES_PRN,
            "product": sp3_name,
            "start_utc": (EPOCH - FRAMES_SPAN_S).isostring(),
            "t_h": np.round(fr["t_h"], 4).tolist(),
            "eci_xyz_km": np.round(fr["eci_xyz_km"], 3).tolist(),
            "ecef_xyz_km": np.round(fr["ecef_xyz_km"], 3).tolist(),
        },
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, separators=(",", ":")))

    print(f"GP source {provenance['source']}: {len(records)} GPS element sets, inclinations {inc_range[0]:.2f} to {inc_range[1]:.2f} deg, "
          f"match residual {provenance['match_max_residual_km']} km")
    print("ground tracks:", ", ".join(t["name"] for t in tracks), f"(max |lat| {max_lat:.2f} deg, max inc {max_inc:.2f} deg)")
    print(f"3-day |r_full - r_twobody| {sso['dr_km'][-1]:.2f} km; |r_full - r_nodrag| {sso['dr_drag_km'][-1]:.4f} km; "
          f"drag daily max {[round(float(x), 4) for x in drag_day_max]} km")
    print(f"SSO inclination {sso['inc_deg']:.3f} deg; final altitude two-body {sso['alt_twobody_km'][-1]:.3f} km, "
          f"full {sso['alt_full_km'][-1]:.3f} km")
    print(f"G{FRAMES_PRN:02d} {sp3_name}: max |r_eci - r_ecef| {radius_diff_m.max():.4f} m over {len(fr['t_h'])} samples")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
