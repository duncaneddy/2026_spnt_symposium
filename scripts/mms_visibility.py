# /// script
# requires-python = ">=3.12"
# dependencies = ["brahe @ git+https://github.com/duncaneddy/brahe@3e2ed7c1739b3f372c35c708702246bbee831183", "numpy"]
# ///
"""GPS satellites usable by MMS 1 over one orbit, main lobe versus main plus side lobes.

The Magnetospheric Multiscale (MMS) spacecraft fly a highly eccentric orbit
whose apogee lies far above the GPS constellation. Above the GPS shell, the
GPS transmit antennas point at the Earth, away from the receiver, so a
receiver there only hears signals that leak past the Earth's limb. This script
counts, every 120 s over one full MMS orbit (perigee to perigee), the GPS
satellites whose signal reaches MMS through the transmit antenna main lobe,
and through the main lobe or the side lobes.

Geometry, per epoch and GPS satellite:
  - Transmitter off-boresight angle: the angle at the GPS satellite between
    its nadir direction (the antenna boresight) and the line to MMS.
  - Main lobe: off-boresight angle <= main_half_angle_deg.
    Main plus side lobes: off-boresight angle <= side_lobe_max_deg.
  - A link never counts when the GPS-to-MMS line passes within Earth radius
    plus 100 km of the geocenter (Earth and lower atmosphere blockage).
  This is a geometric visibility model with no link budget: no transmit
  power, gain pattern shape, path loss or receiver sensitivity is modeled,
  so side-lobe counts are an upper bound on what a real receiver tracks at
  the largest distances.

brahe's access machinery (location_accesses with an AccessPropertyComputer)
takes ground locations fixed in the Earth frame, not a second satellite, so
the off-boresight angle is computed directly from brahe states with numpy.

Data sources:
  - MMS 1 (NORAD 40482) GP elements, from CelesTrak, or from Space-Track
    when CelesTrak does not answer (needs SPACETRACK_USER and SPACETRACK_PASS
    in the environment). Propagated with brahe's SGP4 (its deep-space branch
    applies at this period). SGP4 is a mean-element model with kilometer-level
    errors for this orbit, which is ample for a visibility geometry study.
    Apogee and perigee are taken from the elements.
  - GPS positions from consecutive IGS rapid daily orbit products
    (IGS0OPSRAP, 15 min samples) from the BKG mirror of the IGS archive,
    chained into continuous trajectories. One MMS orbit lasts about 3.5 days,
    so the study runs over the last complete MMS orbit that ends at least two
    days before the GP element epoch, a span for which rapid products are
    published. The span does not contain the talk epoch.

Frames and time:
  - SP3 epochs are GPS time and positions are Earth-fixed (IGS realization of
    ITRF); they are Lagrange-interpolated at each instant. SGP4 output (TEME)
    is rotated by brahe into ITRF with IERS Earth orientation data, so the
    geometry is computed with both satellites in ITRF. Angles and distances
    do not depend on the frame.
  - Positions written for plotting (orbit_xyz_km, gps_xyz_at_apogee_km) are
    GCRF. Epochs are written in UTC.

Receive antenna: MMS spacecraft spin, and each carries several GPS antennas
around its body, so the receiver is treated as having omnidirectional
coverage; no receive-side masking is applied.

Raw downloads are cached in deck/data/raw/mms_visibility/ and reused when
present, so a rerun is offline and reproduces the same output.

Run:
  uv run scripts/mms_visibility.py [--out path.json]

Output (deck/data/mms_visibility.json):
  {generated_utc, gp_source, gps_source, span_utc:[start, end], gps_products,
   object:{name, norad, gp_epoch_utc, perigee_alt_km, apogee_re},
   gps_radius_km,
   pattern:{main_half_angle_deg, side_lobe_max_deg, earth_mask_alt_km, model, source},
   receiver_note,
   t_h:[...], radius_re:[...],
   n_main:[...], n_side:[...],
   orbit_xyz_km:[[x, y, z], ...],
   apogee_t_h, gps_xyz_at_apogee_km:[[x, y, z], ...], gps_lobe_at_apogee:[...],
   frac_time_4plus_main, frac_time_4plus_with_side}
  t_h is hours from the starting perigee, one sample every 120 s.
  n_main counts main-lobe links; n_side counts main-lobe plus side-lobe
  links. gps_lobe_at_apogee is "main", "side" or "none" per row of
  gps_xyz_at_apogee_km. frac_time_* are fractions of the orbit with at least
  four usable satellites.
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
DEFAULT_OUT = ROOT / "deck/data/mms_visibility.json"
RAW_DIR = ROOT / "deck/data/raw/mms_visibility"

NORAD = 40482
STEP_S = 120.0
CELESTRAK_TIMEOUT_S = 10.0
PUBLICATION_LAG_S = 2 * 86400.0

MAIN_HALF_ANGLE_DEG = 23.5
SIDE_LOBE_MAX_DEG = 70.0
EARTH_MASK_ALT_KM = 100.0
PATTERN_SOURCE = (
    "Main lobe: 23.5 deg L1 reference half-beamwidth of the GPS III Space Service Volume "
    "specification, which 'corresponds approximately with the null between the main lobe and "
    "the first side lobe of most GPS satellites' (J. E. Donaldson, J. J. K. Parker, M. C. Moreau, "
    "D. E. Highsmith, P. Martzen, 'Characterization of On-Orbit GPS Transmit Antenna Patterns "
    "for Space Users', NAVIGATION 67(2), 2020, doi:10.1002/navi.361). Side lobes: GPS ACE "
    "reconstructed L1 transmit patterns from GEO flight data agree with ground measurements "
    "'from main lobe out to the second and third sidelobes (70 degrees off boresight)' "
    "(Donaldson et al., ION GNSS+ 2018 presentation, NASA NTRS 20180007029)."
)
RECEIVER_NOTE = (
    "MMS receive antenna coverage is treated as omnidirectional: each spin-stabilized MMS "
    "spacecraft carries several GPS antennas around its body, so no receive-side masking "
    "is applied. Receiver sensitivity is not modeled."
)


def utc_iso(epoch: bh.Epoch) -> str:
    y, mo, d, h, mi, s, _ = epoch.to_datetime()
    return f"{y:04d}-{mo:02d}-{d:02d}T{h:02d}:{mi:02d}:{int(s):02d}Z"


def celestrak_gp() -> list[dict] | None:
    """GP records from CelesTrak, or None when it does not answer in time."""
    result = {}

    def fetch():
        try:
            records = bh.celestrak.CelestrakClient().get_gp(catnr=NORAD)
            result["records"] = [json.loads(r.to_json()) for r in records]
        except Exception as error:
            result["error"] = error

    worker = threading.Thread(target=fetch, daemon=True)
    worker.start()
    worker.join(CELESTRAK_TIMEOUT_S)
    return result.get("records") or None


def spacetrack_gp() -> list[dict]:
    """Newest GP record from Space-Track."""
    client = bh.SpaceTrackClient(os.environ["SPACETRACK_USER"], os.environ["SPACETRACK_PASS"])
    query = (
        bh.SpaceTrackQuery(bh.RequestClass.GP)
        .filter("NORAD_CAT_ID", str(NORAD))
        .order_by("EPOCH", bh.SortOrder.DESC)
        .limit(1)
    )
    return json.loads(client.query_raw(query))


def fetch_gp() -> tuple[bh.GPRecord, str]:
    """MMS 1 GP record and its source, cached in RAW_DIR."""
    cached = sorted(RAW_DIR.glob(f"gp_{NORAD}_*.json"))
    if cached:
        path = cached[0]
    else:
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        records, source = celestrak_gp(), "celestrak"
        if records is None:
            records, source = spacetrack_gp(), "spacetrack"
        path = RAW_DIR / f"gp_{NORAD}_{source}.json"
        path.write_text(json.dumps(records, indent=1))
    source = path.stem.rsplit("_", 1)[1]
    return bh.GPRecord.from_json(json.dumps(json.loads(path.read_text())[0])), source


def fetch_rapid_orbits(start: bh.Epoch, end: bh.Epoch) -> tuple[list[bh.SP3], list[str]]:
    """IGS rapid daily SP3 files covering [start, end] plus a day either side."""
    client = bh.IGSProductsClient(bh.IGSProductSource.BKG)
    products = client.list_products_between(
        start - 86400.0,
        end + 86400.0,
        center=bh.IGSAnalysisCenter.IGS,
        solution=bh.IGSSolutionType.RAPID,
        content=bh.IGSContentType.ORBIT,
        format=bh.IGSFileFormat.SP3,
    )
    products = sorted(products, key=lambda p: p.file_name.start_epoch.mjd())
    for product in products:
        if not (RAW_DIR / product.name).exists():
            client.save(product, str(RAW_DIR))
    return [bh.SP3.from_file(str(RAW_DIR / p.name)) for p in products], [p.name for p in products]


def last_orbit(sgp: bh.SGPPropagator, limit: bh.Epoch, period_s: float) -> tuple[bh.Epoch, int]:
    """Start epoch and sample count of the last perigee-to-perigee orbit ending before limit."""
    t0 = limit - 2.3 * period_s
    epochs = [t0 + k * STEP_S for k in range(int(2.3 * period_s / STEP_S) + 1)]
    r = np.array([np.linalg.norm(s[:3]) for s in sgp.states_ecef(epochs)])
    minima = [k for k in range(1, len(r) - 1) if r[k] < r[k - 1] and r[k] <= r[k + 1]]
    first, second = minima[-2], minima[-1]
    return epochs[first], second - first + 1


def off_boresight_deg(r_gps: np.ndarray, r_rx: np.ndarray) -> np.ndarray:
    """Angle at each GPS satellite between nadir and the line to the receiver [deg]."""
    los = r_rx - r_gps
    cos = np.einsum("ij,ij->i", -r_gps, los) / (np.linalg.norm(r_gps, axis=1) * np.linalg.norm(los, axis=1))
    return np.degrees(np.arccos(np.clip(cos, -1.0, 1.0)))


def earth_blocked(r_gps: np.ndarray, r_rx: np.ndarray, radius_m: float) -> np.ndarray:
    """True where the segment GPS-to-receiver passes within radius_m of the geocenter."""
    d = r_rx - r_gps
    s = np.clip(-np.einsum("ij,ij->i", r_gps, d) / np.einsum("ij,ij->i", d, d), 0.0, 1.0)
    closest = r_gps + s[:, None] * d
    return np.linalg.norm(closest, axis=1) < radius_m


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    out = parser.parse_args().out

    bh.initialize_eop()
    gp, gp_source = fetch_gp()
    sgp = gp.to_sgp_propagator(STEP_S)

    a_km = gp.semimajor_axis
    perigee_alt_km = a_km * (1.0 - gp.eccentricity) - bh.R_EARTH / 1e3
    apogee_re = a_km * (1.0 + gp.eccentricity) / (bh.R_EARTH / 1e3)
    period_s = 86400.0 / gp.mean_motion

    gp_epoch = sgp.epoch
    y, mo, d, *_ = gp_epoch.to_datetime()
    limit = bh.Epoch(y, mo, d, 0, 0, 0.0, 0.0, time_system=bh.UTC) - PUBLICATION_LAG_S
    start, n = last_orbit(sgp, limit, period_s)
    epochs = [start + k * STEP_S for k in range(n)]

    files, product_names = fetch_rapid_orbits(epochs[0], epochs[-1])
    gps = [
        s
        for s in bh.SP3Satellite.from_files(files)
        if s.get_name().startswith("G") and s.start_epoch <= epochs[0] and s.end_epoch >= epochs[-1]
    ]

    # Core computation: MMS and every GPS satellite in ITRF, off-boresight angle and Earth blockage.
    mms_ecef = np.array([s[:3] for s in sgp.states_ecef(epochs)])
    mask_m = bh.R_EARTH + EARTH_MASK_ALT_KM * 1e3
    n_main = np.zeros(n, dtype=int)
    n_side = np.zeros(n, dtype=int)
    lobe = np.full((n, len(gps)), "none", dtype=object)
    gps_radius_km = []
    for j, sat in enumerate(gps):
        r_gps = np.array([sat.state_ecef(t)[:3] for t in epochs])
        gps_radius_km.append(np.linalg.norm(r_gps, axis=1).mean() / 1e3)
        angle = off_boresight_deg(r_gps, mms_ecef)
        clear = ~earth_blocked(r_gps, mms_ecef, mask_m)
        main_lobe = clear & (angle <= MAIN_HALF_ANGLE_DEG)
        any_lobe = clear & (angle <= SIDE_LOBE_MAX_DEG)
        n_main += main_lobe
        n_side += any_lobe
        lobe[any_lobe, j] = "side"
        lobe[main_lobe, j] = "main"

    radius_re = np.linalg.norm(mms_ecef, axis=1) / bh.R_EARTH
    k_apo = int(np.argmax(radius_re))
    t_apo = epochs[k_apo]
    orbit_gcrf_km = np.array([sgp.state_gcrf(t)[:3] for t in epochs]) / 1e3
    gps_apo_gcrf_km = np.array([sat.state_gcrf(t_apo)[:3] for sat in gps]) / 1e3

    frac_main = float(np.mean(n_main >= 4))
    frac_side = float(np.mean(n_side >= 4))

    assert apogee_re > 10, f"apogee {apogee_re:.1f} RE"
    assert np.all(n_side >= n_main), "side-lobe count below main-lobe count"
    assert frac_side > frac_main, f"4+ fractions: side {frac_side:.3f}, main {frac_main:.3f}"
    assert n_main[k_apo] <= 4, f"{n_main[k_apo]} main-lobe satellites at apogee"
    assert 24 <= len(gps) <= 34, f"{len(gps)} GPS satellites"
    assert abs(radius_re.max() - apogee_re) < 0.5, f"propagated apogee {radius_re.max():.2f} RE"

    result = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "gp_source": gp_source,
        "gps_source": "IGS rapid SP3 (IGS0OPSRAP, BKG), consecutive daily files",
        "span_utc": [utc_iso(epochs[0]), utc_iso(epochs[-1])],
        "gps_products": product_names,
        "object": {
            "name": gp.object_name,
            "norad": NORAD,
            "gp_epoch_utc": utc_iso(gp_epoch),
            "perigee_alt_km": round(perigee_alt_km, 1),
            "apogee_re": round(apogee_re, 2),
        },
        "gps_radius_km": round(float(np.mean(gps_radius_km)), 1),
        "pattern": {
            "main_half_angle_deg": MAIN_HALF_ANGLE_DEG,
            "side_lobe_max_deg": SIDE_LOBE_MAX_DEG,
            "earth_mask_alt_km": EARTH_MASK_ALT_KM,
            "model": "geometric, no link budget",
            "source": PATTERN_SOURCE,
        },
        "receiver_note": RECEIVER_NOTE,
        "t_h": [round(k * STEP_S / 3600.0, 4) for k in range(n)],
        "radius_re": [round(float(r), 3) for r in radius_re],
        "n_main": n_main.tolist(),
        "n_side": n_side.tolist(),
        "orbit_xyz_km": [[round(float(c), 1) for c in p] for p in orbit_gcrf_km],
        "apogee_t_h": round(k_apo * STEP_S / 3600.0, 4),
        "gps_xyz_at_apogee_km": [[round(float(c), 1) for c in p] for p in gps_apo_gcrf_km],
        "gps_lobe_at_apogee": lobe[k_apo].tolist(),
        "frac_time_4plus_main": round(frac_main, 4),
        "frac_time_4plus_with_side": round(frac_side, 4),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, separators=(",", ":")))

    print(f"GP {gp.object_name} epoch {result['object']['gp_epoch_utc']} from {gp_source}")
    print(f"perigee alt {perigee_alt_km:.0f} km, apogee {apogee_re:.2f} RE, period {period_s / 3600:.2f} h")
    print(f"span {result['span_utc'][0]} to {result['span_utc'][1]}, {n} samples, {len(gps)} GPS satellites")
    print(f"GPS products: {' '.join(product_names)}")
    print(f"at apogee ({radius_re[k_apo]:.2f} RE): main {n_main[k_apo]}, main+side {n_side[k_apo]}")
    print(f"time with 4+: main {frac_main:.1%}, main+side {frac_side:.1%}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
