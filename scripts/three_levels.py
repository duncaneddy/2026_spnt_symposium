# /// script
# requires-python = ">=3.12"
# dependencies = ["brahe @ git+https://github.com/duncaneddy/brahe@3e2ed7c1739b3f372c35c708702246bbee831183", "numpy"]
# ///
"""Three levels of rigor for "which GPS satellites are above this building right now?".

Computes the azimuth, elevation and Earth-fixed position of every GPS satellite at the
talk epoch, as seen from a point on the Stanford campus, three ways, and measures how far
the two simpler answers are from the precise one.

basic: two-body orbits, a spinning sphere.
  - Each satellite's general perturbations (GP) mean elements are read as osculating
    Keplerian elements. The semi-major axis follows from the GP mean motion by Kepler's
    third law; the mean anomaly is advanced at that mean motion from the element epoch to
    the talk epoch (brahe's Keplerian propagator). No J2 or other perturbation: node,
    perigee and mean motion are frozen at their element values.
  - The element frame (TEME, true equator and mean equinox of the element epoch) is
    treated as inertial and fixed in time.
  - Inertial to Earth-fixed is a single rotation about the z axis by Greenwich mean
    sidereal time from the linear IAU 1982 expression evaluated with UTC in place of UT1.
    This rotation carries the axes from the mean equinox to the Greenwich meridian; it
    neglects polar motion, UT1-UTC, the equation of the equinoxes, and the precession and
    nutation of the element frame between the element epoch and the talk epoch.
  - The station is on a sphere of radius R_EARTH + altitude with the geodetic latitude
    used as a geocentric latitude; elevation is measured from the radial direction.

tle: SGP4 with frame transformations.
  - The same GP elements propagated with SGP4 (brahe), which models the secular and
    periodic J2-J4 effects, lunisolar perturbations and drag the elements were fitted with.
  - SGP4 output (TEME) is rotated to ITRF by brahe's TEME to ITRF transformation (GMST
    rotation and polar motion from Earth orientation parameters).
  - The station is geodetic on the WGS84 ellipsoid; azimuth and elevation are taken in the
    geodetic east-north-zenith frame, as in scripts/skyplot.py.

precise: IGS orbit product, as in scripts/skyplot.py.
  - Satellite positions are interpolated from the newest IGS combined ultra-rapid SP3
    orbit (IGS0OPSULT, BKG mirror) whose span covers the epoch. SP3 epochs are GPS time and
    positions are Earth-fixed (IGS realization of ITRF), so no inertial frame is involved.
  - The station is geodetic on WGS84; azimuth and elevation in the geodetic local frame.

Prediction check (precise):
  - The epoch is in the predicted half of the ultra-rapid product, and no later orbit
    product exists for it yet. The same comparison is made CHECK_DAYS days earlier: the
    ultra-rapid product issued at the same time of day, evaluated the same number of hours
    after its start, against the IGS combined rapid orbit (IGS0OPSRAP) for that day. The
    Earth-fixed position difference per GPS satellite is reported as check.pos_err_m.

Comparison (basic and tle against precise, per satellite, matched by PRN):
  - sky_err_deg: angle between the lines of sight to the level's and the precise satellite
    positions, both seen from the precise (geodetic) station position.
  - el_err_deg: the level's elevation minus the precise elevation, each from the level's
    own station model.
  - pos_err_km: Earth-fixed satellite position difference.
  - mask flips: satellites on opposite sides of the elevation mask from precise.

Data sources:
  - GP elements: CelesTrak `gps-ops` tried first; when it is unreachable, the NAVSTAR
    element sets from Space-Track (needs SPACETRACK_USER and SPACETRACK_PASS). The source is
    recorded as gp_source. Each SP3 GPS satellite is assigned the element set whose SGP4
    ITRF position at the epoch is nearest; the assignment must be one-to-one and within
    50 km.
  - Orbit: IGS combined ultra-rapid SP3 orbit from the BKG mirror.

Time: the talk epoch is UTC; brahe compares instants across UTC, GPS and the GP element
epochs (UTC).

Raw downloads are cached in deck/data/raw/three_levels/ and reused when present.

Run:
  uv run scripts/three_levels.py [--out path.json]

Output (deck/data/three_levels.json):
  {generated_utc, epoch_utc, station:{name, lon_deg, lat_deg, alt_m}, el_mask_deg, product,
   gp_source, gp_epoch_range_utc:[min, max], n_sats,
   levels:[{key:"basic"|"tle", n_visible, visible_prns, sky_err_deg:{median, max},
            el_err_deg:{median, max_abs}, pos_err_km:{median, max}, n_mask_flips,
            flipped_prns},
           {key:"precise", n_visible, visible_prns}],
   check:{epoch_utc, days_before, ultra_rapid_product, rapid_product, n_sats,
          pos_err_m:{median, max}},
   sats:[{prn, az_el_deg:{basic:[az, el], tle:[az, el], precise:[az, el]}}]}
  visible means elevation >= el_mask_deg.
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
DEFAULT_OUT = ROOT / "deck/data/three_levels.json"
SKYPLOT_JSON = ROOT / "deck/data/skyplot.json"
RAW_DIR = ROOT / "deck/data/raw/three_levels"
GP_CACHE = RAW_DIR / "gps-ops.json"
GP_SOURCE_CACHE = RAW_DIR / "gps-ops.source"

EPOCH = bh.Epoch(2026, 11, 12, 19, 0, 0.0, 0.0, time_system=bh.UTC)
STATION = {"name": "STANFORD", "lon_deg": -122.1697, "lat_deg": 37.4275, "alt_m": 30.0}
STATION_LLA = np.array([STATION["lon_deg"], STATION["lat_deg"], STATION["alt_m"]])
EL_MASK_DEG = 10.0
MATCH_KM = 50.0
CHECK_DAYS = 7
LEVELS = ("basic", "tle", "precise")


def covers(name: bh.IGSProductFileName, epoch: bh.Epoch) -> bool:
    return 0.0 <= epoch - name.start_epoch <= name.span


def orbit_file(epoch: bh.Epoch) -> Path:
    """Newest IGS ultra-rapid SP3 file covering the epoch, downloaded into RAW_DIR only when
    absent; the newest cached covering file when the archive cannot be listed."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
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


def check_file(solution: bh.IGSSolutionType, wanted) -> Path:
    """The IGS combined orbit of the given solution type whose file name satisfies `wanted`,
    from RAW_DIR when cached, else downloaded from the BKG mirror."""
    cached = [p for p in RAW_DIR.glob(f"IGS0OPS{solution.code}_*.SP3*") if wanted(bh.IGSProductFileName.parse(p.name))]
    if cached:
        return cached[0]
    client = bh.IGSProductsClient(bh.IGSProductSource.BKG)
    epoch = EPOCH - CHECK_DAYS * 86400.0
    products = client.list_products_between(
        epoch,
        epoch,
        center=bh.IGSAnalysisCenter.IGS,
        solution=solution,
        content=bh.IGSContentType.ORBIT,
        format=bh.IGSFileFormat.SP3,
    )
    product = next(p for p in products if wanted(p.file_name))
    client.save(product, str(RAW_DIR))
    return RAW_DIR / product.name


def prediction_check(product: bh.IGSProductFileName) -> dict:
    """Ultra-rapid against rapid GPS positions CHECK_DAYS before EPOCH, the same time into the
    ultra-rapid product as EPOCH is into `product`."""
    shift = CHECK_DAYS * 86400.0
    epoch = EPOCH - shift
    ult = check_file(bh.IGSSolutionType.ULTRA_RAPID, lambda n: abs(n.start_epoch - (product.start_epoch - shift)) < 1.0)
    rap = check_file(bh.IGSSolutionType.RAPID, lambda n: covers(n, epoch))

    def gps_positions(path: Path) -> dict[str, np.ndarray]:
        sats = bh.SP3.from_file(str(path)).satellites()
        return {s.get_name(): np.array(s.state_ecef(epoch)[:3]) for s in sats if s.get_name().startswith("G")}

    r_ult, r_rap = gps_positions(ult), gps_positions(rap)
    err_m = [float(np.linalg.norm(r_ult[k] - r_rap[k])) for k in sorted(set(r_ult) & set(r_rap))]
    return {
        "epoch_utc": epoch.isostring(),
        "days_before": CHECK_DAYS,
        "ultra_rapid_product": ult.name,
        "rapid_product": rap.name,
        "n_sats": len(err_m),
        "pos_err_m": {"median": round(float(np.median(err_m)), 3), "max": round(max(err_m), 3)},
    }


def gp_records() -> tuple[list[dict], str]:
    """GPS GP records and their source, from the cache, else CelesTrak, else Space-Track."""
    if not (GP_CACHE.exists() and GP_SOURCE_CACHE.exists()):
        try:
            socket.create_connection(("celestrak.org", 443), timeout=5).close()
            query = bh.celestrak.CelestrakQuery.gp.group("gps-ops").format(bh.celestrak.CelestrakOutputFormat.JSON)
            bh.celestrak.CelestrakClient(max_retries=0).download(query, str(GP_CACHE))
            source = "celestrak"
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
            GP_CACHE.write_text(client.query_raw(query))
            source = "spacetrack"
        GP_SOURCE_CACHE.write_text(json.dumps({"source": source}))
    return json.loads(GP_CACHE.read_text()), json.loads(GP_SOURCE_CACHE.read_text())["source"]


def match_to_prns(r_precise: dict[int, np.ndarray], records: list[dict]) -> dict[int, dict]:
    """GP record per PRN: nearest SGP4 ITRF position at EPOCH, one-to-one and within MATCH_KM."""
    sgp_itrf = [bh.GPRecord.from_json(json.dumps(r)).to_sgp_propagator(60.0).state_itrf(EPOCH)[:3] for r in records]
    matched = {}
    for prn, r in r_precise.items():
        dist_km = [np.linalg.norm(r - s) / 1e3 for s in sgp_itrf]
        k = int(np.argmin(dist_km))
        assert dist_km[k] < MATCH_KM, f"G{prn:02d}: nearest GP element set {dist_km[k]:.1f} km"
        matched[prn] = records[k]
    norads = [rec["NORAD_CAT_ID"] for rec in matched.values()]
    assert len(set(norads)) == len(norads), "two PRNs matched the same element set"
    return matched


def azel_geodetic(site_ecef: np.ndarray, sat_ecef: np.ndarray) -> np.ndarray:
    """[az, el] in degrees in the geodetic (WGS84) east-north-zenith frame, as skyplot.py."""
    enz = bh.relative_position_ecef_to_enz(site_ecef, sat_ecef, bh.EllipsoidalConversionType.GEODETIC)
    return np.array(bh.position_enz_to_azel(enz, bh.AngleFormat.DEGREES)[:2])


def basic_position(rec: dict, epoch_gp: bh.Epoch) -> np.ndarray:
    """Earth-fixed position (m) from two-body propagation of the GP elements and one z rotation."""
    n_deg_s = float(rec["MEAN_MOTION"]) * 360.0 / 86400.0
    oe = np.array(
        [
            bh.semimajor_axis(n_deg_s, bh.AngleFormat.DEGREES),
            float(rec["ECCENTRICITY"]),
            float(rec["INCLINATION"]),
            float(rec["RA_OF_ASC_NODE"]),
            float(rec["ARG_OF_PERICENTER"]),
            float(rec["MEAN_ANOMALY"]),
        ]
    )
    r_inertial = bh.KeplerianPropagator.from_keplerian(epoch_gp, oe, bh.AngleFormat.DEGREES, 60.0).state_eci(EPOCH)[:3]

    # Earth spins about z at the sidereal rate: GMST (IAU 1982, linear form) with UT1 = UTC.
    theta = np.radians(280.46061837 + 360.98564736629 * (EPOCH.jd() - 2451545.0))
    rz = np.array([[np.cos(theta), np.sin(theta), 0.0], [-np.sin(theta), np.cos(theta), 0.0], [0.0, 0.0, 1.0]])
    return rz @ r_inertial


def basic_site_and_azel(sat_ecef: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Spherical station (geocentric latitude = geodetic latitude, radius R_EARTH + alt) and
    [az, el] in degrees with elevation measured from the radial direction."""
    lon, lat = np.radians(STATION["lon_deg"]), np.radians(STATION["lat_deg"])
    up = np.array([np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)])
    east = np.array([-np.sin(lon), np.cos(lon), 0.0])
    north = np.cross(up, east)
    site = (bh.R_EARTH + STATION["alt_m"]) * up
    los = sat_ecef - site
    az = np.degrees(np.arctan2(los @ east, los @ north)) % 360.0
    el = np.degrees(np.arcsin(los @ up / np.linalg.norm(los)))
    return site, np.array([az, el])


def angle_deg(u: np.ndarray, v: np.ndarray) -> float:
    return float(np.degrees(np.arctan2(np.linalg.norm(np.cross(u, v)), u @ v)))


def level_summary(key: str, azel: dict, pos: dict, site_ecef: np.ndarray) -> dict:
    prns = sorted(azel["precise"])
    visible = [p for p in prns if azel[key][p][1] >= EL_MASK_DEG]
    out = {"key": key, "n_visible": len(visible), "visible_prns": visible}
    if key == "precise":
        return out
    sky = [angle_deg(pos[key][p] - site_ecef, pos["precise"][p] - site_ecef) for p in prns]
    del_ = [azel[key][p][1] - azel["precise"][p][1] for p in prns]
    dpos = [np.linalg.norm(pos[key][p] - pos["precise"][p]) / 1e3 for p in prns]
    flipped = [p for p in prns if (azel[key][p][1] >= EL_MASK_DEG) != (azel["precise"][p][1] >= EL_MASK_DEG)]
    return out | {
        "sky_err_deg": {"median": round(float(np.median(sky)), 3), "max": round(max(sky), 3)},
        "el_err_deg": {"median": round(float(np.median(del_)), 3), "max_abs": round(float(np.max(np.abs(del_))), 3)},
        "pos_err_km": {"median": round(float(np.median(dpos)), 3), "max": round(float(max(dpos)), 3)},
        "n_mask_flips": len(flipped),
        "flipped_prns": flipped,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    out = parser.parse_args().out

    bh.initialize_eop()
    path = orbit_file(EPOCH)
    records, gp_source = gp_records()

    # precise: IGS SP3 (ITRF) at the epoch, geodetic station, geodetic local frame.
    sp3 = bh.SP3.from_file(str(path))
    site_ecef = bh.position_geodetic_to_ecef(STATION_LLA, bh.AngleFormat.DEGREES)
    gps = [s for s in sp3.satellites() if s.get_name().startswith("G")]
    pos = {"precise": {int(s.get_name()[1:]): np.array(s.state_ecef(EPOCH)[:3]) for s in gps}}
    azel = {"precise": {p: azel_geodetic(site_ecef, r) for p, r in pos["precise"].items()}}

    # tle: SGP4 (TEME) rotated to ITRF by brahe, geodetic station, geodetic local frame.
    gp = match_to_prns(pos["precise"], records)
    sgp = {p: bh.GPRecord.from_json(json.dumps(rec)).to_sgp_propagator(60.0) for p, rec in gp.items()}
    pos["tle"] = {p: np.array(prop.state_itrf(EPOCH)[:3]) for p, prop in sgp.items()}
    azel["tle"] = {p: azel_geodetic(site_ecef, r) for p, r in pos["tle"].items()}

    # basic: two-body from the GP elements, one z rotation, spherical station, radial vertical.
    pos["basic"] = {p: basic_position(gp[p], sgp[p].epoch) for p in gp}
    azel["basic"] = {p: basic_site_and_azel(r)[1] for p, r in pos["basic"].items()}

    levels = [level_summary(k, azel, pos, site_ecef) for k in LEVELS]
    check = prediction_check(bh.IGSProductFileName.parse(path.name))
    gp_epochs = sorted(prop.epoch.isostring() for prop in sgp.values())
    prns = sorted(pos["precise"])
    skyplot_visible = [s["prn"] for s in json.loads(SKYPLOT_JSON.read_text())["sats"] if s["visible"]]
    by_key = {lv["key"]: lv for lv in levels}

    assert 24 <= len(prns) <= 34, f"{len(prns)} GPS satellites"
    assert all(set(azel[k]) == set(prns) for k in LEVELS), "satellite missing a solution"
    assert by_key["precise"]["visible_prns"] == sorted(skyplot_visible), "precise visible set differs from skyplot"
    assert 0.05 <= by_key["tle"]["pos_err_km"]["median"] <= 20.0, f"tle median {by_key['tle']['pos_err_km']}"
    assert by_key["tle"]["sky_err_deg"]["median"] < 0.1, f"tle sky median {by_key['tle']['sky_err_deg']}"
    assert by_key["basic"]["pos_err_km"]["median"] > by_key["tle"]["pos_err_km"]["median"], "basic pos <= tle"
    assert by_key["basic"]["sky_err_deg"]["median"] > by_key["tle"]["sky_err_deg"]["median"], "basic sky <= tle"
    assert all(-90.0 <= azel[k][p][1] <= 90.0 for k in LEVELS for p in prns), "elevation out of range"
    assert check["n_sats"] >= 24, f"prediction check on {check['n_sats']} satellites"
    assert 0.001 <= check["pos_err_m"]["median"] <= 1.0, f"prediction check median {check['pos_err_m']}"

    result = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "epoch_utc": EPOCH.isostring(),
        "station": STATION,
        "el_mask_deg": EL_MASK_DEG,
        "product": path.name,
        "gp_source": gp_source,
        "gp_epoch_range_utc": [gp_epochs[0], gp_epochs[-1]],
        "n_sats": len(prns),
        "levels": levels,
        "check": check,
        "sats": [
            {"prn": p, "az_el_deg": {k: [round(float(v), 3) for v in azel[k][p]] for k in LEVELS}} for p in prns
        ],
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, separators=(",", ":")))

    print(f"product {path.name}; GP source {gp_source}; GP epochs {gp_epochs[0]} .. {gp_epochs[-1]}")
    print(f"{len(prns)} GPS satellites at {result['epoch_utc']}, mask {EL_MASK_DEG:.0f} deg")
    for lv in levels:
        line = f"{lv['key']:8s} {lv['n_visible']:2d} visible: " + " ".join(f"G{p:02d}" for p in lv["visible_prns"])
        if "sky_err_deg" in lv:
            line += (
                f"\n         sky err median {lv['sky_err_deg']['median']} max {lv['sky_err_deg']['max']} deg;"
                f" el err median {lv['el_err_deg']['median']} max|.| {lv['el_err_deg']['max_abs']} deg;"
                f" pos err median {lv['pos_err_km']['median']} max {lv['pos_err_km']['max']} km;"
                f" mask flips {lv['n_mask_flips']} {lv['flipped_prns']}"
            )
        print(line)
    print(
        f"check {check['ultra_rapid_product']} vs {check['rapid_product']} at {check['epoch_utc']}:"
        f" {check['n_sats']} satellites, median {check['pos_err_m']['median']} max {check['pos_err_m']['max']} m"
    )
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
