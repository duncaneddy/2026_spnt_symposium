# /// script
# requires-python = ">=3.12"
# dependencies = ["brahe @ git+https://github.com/duncaneddy/brahe@sp3/9-igs-rate-limit", "numpy"]
# ///
"""A LEO PNT Walker constellation, propagated in parallel, compared with GPS.

Builds the 53 degree Walker delta shell of Xona Space Systems' Pulsar LEO PNT
constellation with brahe's Walker generator, propagates every satellite for one
orbital period with a high-fidelity numerical force model, once in a plain
serial loop and once with brahe's parallel propagator, and times both. Then
counts the satellites in view above a 10 degree elevation mask and computes
PDOP on a grid of latitudes (0 to 80 deg in 10 deg steps, 12 longitudes,
30 epochs), for the Walker shell and for GPS from an IGS orbit product.

Constellation (source in config.source of the output):
  - Xona's published design: 258 satellites at 1080 km, 12 planes of 16 at
    53 deg plus 6 planes of 11 at 97 deg. This script models the 53 deg shell
    (192 satellites, 12 planes) as a Walker delta. The phasing factor f = 1 is
    this script's assumption (not published), as are the satellite mass,
    areas and coefficients.

Force model and integrator:
  - EGM2008 gravity 20x20, NRLMSISE-00 drag (brahe's space-weather data),
    solar radiation pressure with a conical eclipse, Sun and Moon third body
    (low-precision ephemerides). RKF78 with abs 1e-6, rel 1e-12.

Data source for GPS:
  - IGS combined ultra-rapid orbit (IGS0OPSULT, 15 min samples, 48 h span)
    covering the talk epoch, from the BKG mirror of the IGS archive.

Frames and time:
  - Walker initial states are GCRF at the talk epoch (UTC) and are propagated
    in GCRF. For visibility they are rotated to ITRF with brahe's IERS EOP data.
  - SP3 epochs are GPS time and positions are Earth-fixed (IGS realization of
    ITRF); they are interpolated in that frame. GPS is sampled at 30 epochs
    spread over the SP3 coverage, the Walker shell at 30 epochs spread over
    its one-orbit propagation span.
  - Elevation is measured from the WGS84 geodetic horizontal plane at each grid
    point (on the ellipsoid surface). PDOP uses the geometry matrix of unit
    line-of-sight vectors plus a clock column for satellites above the mask;
    samples with fewer than 4 satellites are skipped and counted.

Raw downloads are cached in deck/data/raw/walker_pnt/ and reused when present.

Run:
  uv run scripts/walker_pnt.py [--out path.json]

Output (deck/data/walker_pnt.json):
  {generated_utc, config:{pattern, t, p, f, alt_km, inc_deg, source,
   force_model, integrator, mass_kg, drag_area_m2, cd, srp_area_m2, cr},
   span_h, threads, wall_s_serial, wall_s_parallel, speedup,
   snapshot_xyz_km:[[x, y, z], ...] (GCRF, start epoch),
   planes:[int, ...] (plane index per snapshot row),
   one_orbit_xyz_km:[[x, y, z], ...] (GCRF, satellite 0, 60 s steps),
   in_view:{lat_deg, walker_mean, gps_mean, el_mask_deg},
   dop:{lat_deg, walker_pdop_median, gps_pdop_median,
        skipped:{walker, gps}, samples_per_lat}}
  A median PDOP is null at a latitude where no sample has 4 satellites in view.
"""

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import brahe as bh
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "deck/data/walker_pnt.json"
RAW_DIR = ROOT / "deck/data/raw/walker_pnt"

EPOCH = bh.Epoch(2026, 11, 12, 19, 0, 0.0, 0.0, time_system=bh.UTC)

T, P, F = 192, 12, 1
ALT_KM = 1080.0
INC_DEG = 53.0
SOURCE = (
    "Xona Space Systems, Pulsar constellation (xonaspace.com/technology): 258 satellites at 1080 km, "
    "12 planes of 16 at 53 deg and 6 planes of 11 at 97 deg. From the source: t=192, p=12, 1080 km, 53 deg "
    "(the 53 deg shell). Assumed here: Walker delta pattern, phasing f=1, circular orbits, the 97 deg shell "
    "(66 satellites) not modeled, and the satellite mass, areas and coefficients."
)

MASS_KG = 100.0
AREA_M2 = 1.0
CD = 2.2
CR = 1.3

EL_MASK_DEG = 10.0
LATS_DEG = np.arange(0.0, 81.0, 10.0)
LONS_DEG = np.arange(0.0, 360.0, 30.0)
N_EPOCHS = 30


def force_model() -> bh.ForceModelConfig:
    return bh.ForceModelConfig(
        gravity=bh.GravityConfiguration(degree=20, order=20),
        drag=bh.DragConfiguration(
            bh.AtmosphericModel.NRLMSISE00,
            bh.ParameterSource.parameter_index(1),
            bh.ParameterSource.parameter_index(2),
        ),
        srp=bh.SolarRadiationPressureConfiguration(
            bh.ParameterSource.parameter_index(3),
            bh.ParameterSource.parameter_index(4),
            bh.EclipseModel.CONICAL,
        ),
        third_body=[
            bh.ThirdBodyConfiguration(bh.ThirdBody.SUN, bh.EphemerisSource.LowPrecision),
            bh.ThirdBodyConfiguration(bh.ThirdBody.MOON, bh.EphemerisSource.LowPrecision),
        ],
        mass=bh.ParameterSource.parameter_index(0),
    )


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


def grid_sites() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """ECEF positions [m] and geodetic up unit vectors of the lat x lon grid, with each site's latitude."""
    lat, lon = np.meshgrid(LATS_DEG, LONS_DEG, indexing="ij")
    lat, lon = lat.ravel(), lon.ravel()
    pos = np.array(
        [bh.position_geodetic_to_ecef(np.array([lo, la, 0.0]), bh.AngleFormat.DEGREES) for la, lo in zip(lat, lon)]
    )
    phi, lam = np.radians(lat), np.radians(lon)
    up = np.column_stack([np.cos(phi) * np.cos(lam), np.cos(phi) * np.sin(lam), np.sin(phi)])
    return pos, up, lat


def visibility_and_pdop(sat_ecef: np.ndarray, sites: np.ndarray, up: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Satellites above the mask and PDOP (NaN when fewer than 4) for each site, at one instant."""
    los = sat_ecef[None, :, :] - sites[:, None, :]
    los /= np.linalg.norm(los, axis=2, keepdims=True)
    el = np.degrees(np.arcsin(np.einsum("skx,sx->sk", los, up)))
    n_view = (el >= EL_MASK_DEG).sum(axis=1)
    pdop = np.full(len(sites), np.nan)
    for s in range(len(sites)):
        u = los[s, el[s] >= EL_MASK_DEG]
        if len(u) < 4:
            continue
        g = np.column_stack([-u, np.ones(len(u))])
        q = np.linalg.inv(g.T @ g)
        pdop[s] = np.sqrt(np.trace(q[:3, :3]))
    return n_view, pdop


def grid_statistics(sat_ecef_at_epochs: list[np.ndarray]) -> tuple[list[float], list[float | None], int]:
    """Mean satellites in view and median PDOP per latitude over all longitudes and epochs.

    The median PDOP is None at a latitude where every sample has fewer than 4 satellites in view.
    """
    sites, up, site_lat = grid_sites()
    n_view, pdop = zip(*(visibility_and_pdop(x, sites, up) for x in sat_ecef_at_epochs))
    n_view, pdop = np.array(n_view), np.array(pdop)
    mean_view = [float(n_view[:, site_lat == la].mean()) for la in LATS_DEG]
    median_pdop = []
    for la in LATS_DEG:
        values = pdop[:, site_lat == la]
        values = values[~np.isnan(values)]
        median_pdop.append(float(np.median(values)) if values.size else None)
    return mean_view, median_pdop, int(np.isnan(pdop).sum())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    out = parser.parse_args().out

    bh.initialize_eop()
    bh.initialize_sw()

    # Generate the Walker constellation.
    walker = (
        bh.WalkerConstellationGenerator.builder(T, P, F, bh.R_EARTH + ALT_KM * 1e3, INC_DEG, EPOCH)
        .pattern(bh.WalkerPattern.DELTA)
        .base_name("PULSAR")
        .build()
    )
    prop_config = (
        bh.NumericalPropagationConfig.with_method(bh.IntegrationMethod.RKF78).with_abs_tol(1e-6).with_rel_tol(1e-12)
    )
    params = np.array([MASS_KG, AREA_M2, CD, AREA_M2, CR])
    span_s = bh.orbital_period(walker.semi_major_axis)
    t_end = EPOCH + span_s

    # Propagate one orbit: a plain loop, then in parallel.
    serial = walker.as_numerical_propagators(prop_config, force_model(), params)
    t0 = time.perf_counter()
    for prop in serial:
        prop.propagate_to(t_end)
    wall_serial = time.perf_counter() - t0

    props = walker.as_numerical_propagators(prop_config, force_model(), params)
    t0 = time.perf_counter()
    bh.par_propagate_to(props, t_end)
    wall_parallel = time.perf_counter() - t0
    threads = bh.get_max_threads()

    sats_per_plane = walker.satellites_per_plane
    planes = [i // sats_per_plane for i in range(len(props))]
    snapshot = np.array([p.state_gcrf(EPOCH)[:3] for p in props]) / 1e3
    one_orbit = np.array([props[0].state_gcrf(EPOCH + dt)[:3] for dt in np.arange(0.0, span_s, 60.0)]) / 1e3
    final_radius_km = np.array([np.linalg.norm(p.current_state()[:3]) for p in props]) / 1e3
    serial_par_diff_m = max(
        float(np.linalg.norm(a.current_state()[:3] - b.current_state()[:3])) for a, b in zip(serial, props)
    )

    # Satellites in view and PDOP on the latitude grid.
    walker_epochs = [EPOCH + span_s * (k + 0.5) / N_EPOCHS for k in range(N_EPOCHS)]
    walker_ecef = [np.array([p.state_itrf(t)[:3] for p in props]) for t in walker_epochs]
    walker_view, walker_pdop, walker_skipped = grid_statistics(walker_ecef)

    client = bh.IGSProductsClient(bh.IGSProductSource.BKG)
    product = newest_product_covering(client, EPOCH)
    sp3 = bh.SP3.from_file(str(fetch_sp3(product, client)))
    gps = [s for s in sp3.satellites() if s.get_name().startswith("G")]
    sp3_start, sp3_span = sp3.start_epoch, sp3.end_epoch - sp3.start_epoch
    gps_epochs = [sp3_start + sp3_span * (k + 0.5) / N_EPOCHS for k in range(N_EPOCHS)]
    gps_ecef = [np.array([s.state_ecef(t)[:3] for s in gps]) for t in gps_epochs]
    gps_view, gps_pdop, gps_skipped = grid_statistics(gps_ecef)

    speedup = wall_serial / wall_parallel
    if threads >= 4:
        assert speedup > 1.5, f"speedup {speedup:.2f} on {threads} threads"
    r_nom_km = (bh.R_EARTH / 1e3) + ALT_KM
    assert np.all(np.abs(final_radius_km - r_nom_km) < 20.0), "final radius off nominal"
    peak = int(np.argmax(walker_view))
    assert INC_DEG - 20.0 <= LATS_DEG[peak] <= INC_DEG, f"walker in-view peak at {LATS_DEG[peak]:.0f} deg"
    assert walker_view[peak] > gps_view[peak], "walker does not exceed GPS at its in-view peak"
    assert all(v is None or v > 0.0 for v in walker_pdop + gps_pdop), "non-positive PDOP"
    assert all(v is not None for v in gps_pdop), "GPS PDOP undefined at a latitude"

    result = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "config": {
            "pattern": "delta",
            "t": T,
            "p": P,
            "f": F,
            "alt_km": ALT_KM,
            "inc_deg": INC_DEG,
            "source": SOURCE,
            "force_model": "EGM2008 20x20, NRLMSISE-00 drag, SRP (conical eclipse), Sun and Moon third body",
            "integrator": "RKF78, abs tol 1e-6, rel tol 1e-12",
            "mass_kg": MASS_KG,
            "drag_area_m2": AREA_M2,
            "cd": CD,
            "srp_area_m2": AREA_M2,
            "cr": CR,
        },
        "span_h": round(span_s / 3600.0, 4),
        "threads": threads,
        "wall_s_serial": round(wall_serial, 3),
        "wall_s_parallel": round(wall_parallel, 3),
        "speedup": round(speedup, 2),
        "snapshot_xyz_km": np.round(snapshot, 1).tolist(),
        "planes": planes,
        "one_orbit_xyz_km": np.round(one_orbit, 1).tolist(),
        "in_view": {
            "lat_deg": LATS_DEG.tolist(),
            "walker_mean": [round(v, 2) for v in walker_view],
            "gps_mean": [round(v, 2) for v in gps_view],
            "el_mask_deg": EL_MASK_DEG,
        },
        "dop": {
            "lat_deg": LATS_DEG.tolist(),
            "walker_pdop_median": [None if v is None else round(v, 3) for v in walker_pdop],
            "gps_pdop_median": [round(v, 3) for v in gps_pdop],
            "skipped": {"walker": walker_skipped, "gps": gps_skipped},
            "samples_per_lat": len(LONS_DEG) * N_EPOCHS,
        },
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, separators=(",", ":")))

    print(f"Walker delta {T}/{P}/{F} at {ALT_KM:.0f} km, {INC_DEG:.0f} deg; span {span_s / 60:.1f} min")
    print(f"serial {wall_serial:.2f} s, parallel {wall_parallel:.2f} s on {threads} threads, speedup {speedup:.2f}")
    print(f"max serial vs parallel final position difference {serial_par_diff_m:.3e} m")
    print(f"final radius {final_radius_km.min():.1f} to {final_radius_km.max():.1f} km (nominal {r_nom_km:.1f})")
    print(f"GPS product {product.name}, {len(gps)} satellites")
    print("lat  walker_in_view  gps_in_view  walker_pdop  gps_pdop")
    for la, wv, gv, wp, gp in zip(LATS_DEG, walker_view, gps_view, walker_pdop, gps_pdop):
        wp_text = "-" if wp is None else f"{wp:.2f}"
        print(f"{la:3.0f}  {wv:14.2f}  {gv:11.2f}  {wp_text:>11}  {gp:8.2f}")
    print(f"PDOP samples skipped (<4 in view): walker {walker_skipped}, gps {gps_skipped}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
