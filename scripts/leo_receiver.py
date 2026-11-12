# /// script
# requires-python = ">=3.12"
# dependencies = ["brahe @ git+https://github.com/duncaneddy/brahe@3e2ed7c1739b3f372c35c708702246bbee831183", "numpy"]
# ///
"""Number of GPS satellites in view of a receiver on the ground versus on the ISS.

One function, visible_count(receiver_ecef, epochs), counts the GPS satellites a
zenith-pointing antenna sees. It takes any callable that returns the receiver's
Earth-fixed position at an epoch. It is called once with a fixed Stanford
campus station and once with the International Space Station; the two calls
differ only in that argument.

Visibility rule (identical for both receivers):
  - the satellite is at least 5 degrees above the receiver's local horizontal
    plane, the plane normal to the geodetic (WGS84 ellipsoid) up direction at
    the receiver, and
  - the straight line from the receiver to the satellite does not pass through
    the Earth, modeled as the WGS84 ellipsoid (z stretched by a/b to make it a
    sphere of the equatorial radius).
No antenna gain pattern, signal power or obstruction other than the Earth is
modeled.

Data sources:
  - GPS satellite positions: IGS combined ultra-rapid orbit (IGS0OPSULT, 15 min
    samples, 48 h span) from the BKG mirror of the IGS archive, which needs no
    login. The newest issue whose span covers both ends of the analysis window
    is used.
  - ISS orbit: NORAD 25544 general-perturbations (GP) elements from CelesTrak,
    falling back to Space-Track when CelesTrak does not answer within
    CELESTRAK_TIMEOUT_S. The source used is recorded as gp_source. Elements are
    propagated with SGP4.

Frames and time:
  - All visibility geometry is in one Earth-fixed frame, ITRF (IGS realization
    for the SP3 satellites). SP3 states are already Earth-fixed; the SGP4
    output (TEME) is converted to ITRF with brahe, using Earth orientation
    parameters.
  - SP3 epochs are GPS time; the talk epoch and the analysis grid are UTC.
    brahe compares absolute instants across time systems.
  - orbit_xyz_km (ISS path) and links_at_epoch positions are GCRF, for drawing
    an inertial picture; the counts do not depend on that frame.

Analysis window: the talk epoch to two ISS orbital periods later (period from
the mean motion of the GP elements) at 30 s spacing. Raw downloads are cached in
deck/data/raw/leo_receiver/ and reused when present.

Run:
  uv run scripts/leo_receiver.py [--out path.json]

Output (deck/data/leo_receiver.json):
  {generated_utc, epoch_utc, product, gp_source, gp_epoch_utc, el_mask_deg,
   receiver:{name, norad, alt_km}, ground_station:{name, lat_deg, lon_deg, alt_m},
   t_min:[...], n_visible_leo:[...], n_visible_ground:[...], mean_leo, mean_ground,
   orbit_xyz_km:[[x, y, z], ...] (ISS, GCRF, same grid as t_min),
   links_at_epoch:{rx_xyz_km, gps_xyz_km:[[x, y, z], ...], visible:[bool, ...]}}
  receiver.alt_km is the mean geodetic altitude over the window; links_at_epoch
  positions are GCRF at the talk epoch.
"""

import argparse
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import brahe as bh
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "deck/data/leo_receiver.json"
RAW_DIR = ROOT / "deck/data/raw/leo_receiver"
GP_CACHE = RAW_DIR / "iss_gp.json"
GP_SOURCE_CACHE = RAW_DIR / "iss_gp_source.txt"

EPOCH = bh.Epoch(2026, 11, 12, 19, 0, 0.0, 0.0, time_system=bh.UTC)
STANFORD = {"name": "STANFORD", "lat_deg": 37.4275, "lon_deg": -122.1697, "alt_m": 30.0}
ISS_NORAD = 25544
EL_MASK_DEG = 5.0
STEP_S = 30.0
N_ORBITS = 2
CELESTRAK_TIMEOUT_S = 10.0
AXIS_SCALE = np.array([1.0, 1.0, 1.0 / (1.0 - bh.WGS84_F)])


def fetch_gp() -> tuple[dict, str]:
    """ISS GP record and the source that supplied it, cached after the first call."""
    if not GP_CACHE.exists():
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        records, source = None, "celestrak"
        query = bh.celestrak.CelestrakQuery.gp.catnr(ISS_NORAD).format(bh.celestrak.CelestrakOutputFormat.JSON)
        tmp = RAW_DIR / "iss_gp_celestrak.json"
        worker = threading.Thread(
            target=lambda: bh.celestrak.CelestrakClient(max_retries=0).download(query, str(tmp)), daemon=True
        )
        worker.start()
        worker.join(CELESTRAK_TIMEOUT_S)
        if not worker.is_alive() and tmp.exists():
            records = tmp.read_text()
        else:
            print(f"CelesTrak did not answer within {CELESTRAK_TIMEOUT_S:.0f} s; using Space-Track")
            client = bh.SpaceTrackClient(os.environ["SPACETRACK_USER"], os.environ["SPACETRACK_PASS"])
            records = client.query_raw(
                bh.SpaceTrackQuery(bh.RequestClass.GP)
                .filter("NORAD_CAT_ID", str(ISS_NORAD))
                .order_by("EPOCH", bh.SortOrder.DESC)
                .limit(1)
            )
            source = "spacetrack"
        GP_CACHE.write_text(records)
        GP_SOURCE_CACHE.write_text(source)
    return json.loads(GP_CACHE.read_text())[0], GP_SOURCE_CACHE.read_text().strip()


def newest_product_covering(client: bh.IGSProductsClient, start: bh.Epoch, end: bh.Epoch) -> bh.IGSProduct:
    """Latest-starting IGS ultra-rapid SP3 product whose span contains [start, end]."""
    products = client.list_products_between(
        start,
        end,
        center=bh.IGSAnalysisCenter.IGS,
        solution=bh.IGSSolutionType.ULTRA_RAPID,
        content=bh.IGSContentType.ORBIT,
        format=bh.IGSFileFormat.SP3,
    )
    covering = [
        p for p in products if 0.0 <= start - p.file_name.start_epoch and end - p.file_name.start_epoch <= p.file_name.span
    ]
    if not covering:
        raise RuntimeError(f"no IGS ultra-rapid product covers {start} to {end}")
    return min(covering, key=lambda p: start - p.file_name.start_epoch)


def fetch_sp3(product: bh.IGSProduct, client: bh.IGSProductsClient) -> Path:
    """Product file in RAW_DIR as published, downloaded only when absent."""
    path = RAW_DIR / product.name
    if not path.exists():
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        client.save(product, str(RAW_DIR))
    return path


def visible_count(receiver_ecef: Callable[[bh.Epoch], np.ndarray], gps_sats, epochs: list[bh.Epoch]):
    """GPS satellites in view of a receiver at each epoch.

    receiver_ecef(epoch) returns the receiver's ITRF position [x, y, z] in m.
    Returns (counts, visible) with counts shaped (n_epochs,) and visible a
    boolean array shaped (n_epochs, n_sats).
    """
    visible = np.zeros((len(epochs), len(gps_sats)), dtype=bool)
    for i, t in enumerate(epochs):
        rx = np.asarray(receiver_ecef(t))[:3]
        for j, sat in enumerate(gps_sats):
            sat_ecef = sat.state_ecef(t)[:3]
            e, n, u = bh.relative_position_ecef_to_enz(rx, sat_ecef, bh.EllipsoidalConversionType.GEODETIC)
            above_mask = np.degrees(np.arctan2(u, np.hypot(e, n))) >= EL_MASK_DEG
            rx_s, los = rx * AXIS_SCALE, (sat_ecef - rx) * AXIS_SCALE
            s = np.clip(-rx_s @ los / (los @ los), 0.0, 1.0)
            clear = np.linalg.norm(rx_s + s * los) > bh.R_EARTH
            visible[i, j] = above_mask and clear
    return visible.sum(axis=1), visible


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    out = parser.parse_args().out

    bh.initialize_eop()

    gp, gp_source = fetch_gp()
    iss = bh.GPRecord.from_json(json.dumps(gp)).to_sgp_propagator(STEP_S)
    period_s = 86400.0 / float(gp["MEAN_MOTION"])
    n_steps = int(N_ORBITS * period_s // STEP_S)
    t_s = STEP_S * np.arange(n_steps + 1)
    epochs = [EPOCH + float(dt) for dt in t_s]

    client = bh.IGSProductsClient(bh.IGSProductSource.BKG)
    product = newest_product_covering(client, EPOCH, epochs[-1])
    sp3 = bh.SP3.from_file(str(fetch_sp3(product, client)))
    gps_sats = sorted((s for s in sp3.satellites() if s.get_name().startswith("G")), key=lambda s: s.get_name())

    # Core computation: the same function, two receivers.
    site_ecef = bh.position_geodetic_to_ecef(
        np.array([STANFORD["lon_deg"], STANFORD["lat_deg"], STANFORD["alt_m"]]), bh.AngleFormat.DEGREES
    )
    n_ground, _ = visible_count(lambda t: site_ecef, gps_sats, epochs)
    n_leo, visible_leo = visible_count(lambda t: iss.state_itrf(t)[:3], gps_sats, epochs)

    iss_gcrf = np.array(iss.states_gcrf(epochs))[:, :3]
    iss_itrf = np.array(iss.states_itrf(epochs))[:, :3]
    alt_km = np.array(
        [bh.position_ecef_to_geodetic(r, bh.AngleFormat.DEGREES)[2] for r in iss_itrf]
    ) / 1e3
    gps_gcrf = np.array([s.state_eci(EPOCH)[:3] for s in gps_sats]) / 1e3

    mean_leo, mean_ground = float(n_leo.mean()), float(n_ground.mean())

    assert abs(mean_leo - mean_ground) < 2.0, f"mean LEO {mean_leo:.2f} vs ground {mean_ground:.2f}"
    assert n_leo.min() >= 4 and n_leo.max() <= 20, f"LEO counts {n_leo.min()}..{n_leo.max()}"
    assert n_ground.min() >= 4 and n_ground.max() <= 20, f"ground counts {n_ground.min()}..{n_ground.max()}"
    assert 380.0 < alt_km.mean() < 440.0, f"ISS altitude {alt_km.mean():.1f} km"

    result = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "epoch_utc": "2026-11-12T19:00:00Z",
        "product": product.name,
        "gp_source": gp_source,
        "gp_epoch_utc": gp["EPOCH"],
        "el_mask_deg": EL_MASK_DEG,
        "receiver": {"name": gp["OBJECT_NAME"], "norad": ISS_NORAD, "alt_km": round(float(alt_km.mean()), 1)},
        "ground_station": STANFORD,
        "t_min": np.round(t_s / 60.0, 4).tolist(),
        "n_visible_leo": n_leo.tolist(),
        "n_visible_ground": n_ground.tolist(),
        "mean_leo": round(mean_leo, 2),
        "mean_ground": round(mean_ground, 2),
        "orbit_xyz_km": np.round(iss_gcrf / 1e3, 2).tolist(),
        "links_at_epoch": {
            "rx_xyz_km": np.round(iss_gcrf[0] / 1e3, 2).tolist(),
            "gps_xyz_km": np.round(gps_gcrf, 2).tolist(),
            "visible": [bool(v) for v in visible_leo[0]],
        },
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, separators=(",", ":")))

    print(f"product {product.name}; GP source {gp_source}, element epoch {gp['EPOCH']}")
    print(f"{len(gps_sats)} GPS satellites, {len(epochs)} epochs over {t_s[-1] / 60:.1f} min ({N_ORBITS} orbits)")
    print(f"ISS mean altitude {alt_km.mean():.1f} km (min {alt_km.min():.1f}, max {alt_km.max():.1f})")
    print(f"ISS    visible: mean {mean_leo:.2f}, min {n_leo.min()}, max {n_leo.max()}")
    print(f"ground visible: mean {mean_ground:.2f}, min {n_ground.min()}, max {n_ground.max()}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
