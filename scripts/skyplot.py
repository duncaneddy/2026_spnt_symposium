# /// script
# requires-python = ">=3.12"
# dependencies = ["brahe @ git+https://github.com/duncaneddy/brahe@sp3/9-igs-rate-limit", "numpy"]
# ///
"""GPS satellite sky plot at the talk epoch from an IGS ultra-rapid orbit product.

Computes the azimuth and elevation of every GPS satellite in the newest IGS
ultra-rapid SP3 orbit that covers the talk epoch, as seen from a point on the
Stanford campus, together with the satellite's azimuth/elevation track from one
hour before to one hour after the epoch at 60 s spacing (samples below the
horizon are dropped).

Data source:
  - IGS combined ultra-rapid orbit (IGS0OPSULT, 15 min samples, 48 h span, the
    first 24 h fitted to observations and the last 24 h predicted) from the BKG
    mirror of the IGS archive, which needs no login. The newest issue whose
    span covers the epoch is selected, so rerunning after a later issue is
    published picks it up.

Frames and time:
  - SP3 epochs are GPS time and positions are Earth-fixed (IGS realization of
    ITRF). Satellite positions are interpolated at the requested instant in
    that frame (Lagrange polynomial through the neighboring samples) and
    rotated into the station's local east-north-zenith frame on the WGS84
    ellipsoid, so no inertial frame or Earth-orientation data is involved.
  - Azimuth is measured clockwise from north, elevation above the local
    horizontal plane. No refraction or antenna effects are modeled.

Raw downloads are cached in deck/data/raw/skyplot/ and reused when present.

Run:
  uv run scripts/skyplot.py [--out path.json]

Output (deck/data/skyplot.json):
  {generated_utc, epoch_utc, product,
   station:{name, lat_deg, lon_deg, alt_m}, el_mask_deg,
   sats:[{prn, az_deg, el_deg, visible, track_azel_deg:[[az, el], ...]}],
   n_visible}
  visible means el_deg >= el_mask_deg at the epoch.
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import brahe as bh
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "deck/data/skyplot.json"
RAW_DIR = ROOT / "deck/data/raw/skyplot"

EPOCH = bh.Epoch(2026, 11, 12, 19, 0, 0.0, 0.0, time_system=bh.UTC)
STANFORD = {"name": "STANFORD", "lat_deg": 37.4275, "lon_deg": -122.1697, "alt_m": 30.0}
EL_MASK_DEG = 10.0
TRACK_OFFSETS_S = range(-3600, 3601, 60)


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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    out = parser.parse_args().out

    client = bh.IGSProductsClient(bh.IGSProductSource.BKG)
    product = newest_product_covering(client, EPOCH)
    path = fetch_sp3(product, client)

    # Core computation: interpolate each satellite in ITRF and rotate to local ENZ.
    sp3 = bh.SP3.from_file(str(path))
    site = np.array([STANFORD["lon_deg"], STANFORD["lat_deg"], STANFORD["alt_m"]])
    site_ecef = bh.position_geodetic_to_ecef(site, bh.AngleFormat.DEGREES)

    def azel(sat, t):
        enz = bh.relative_position_ecef_to_enz(
            site_ecef, sat.state_ecef(t)[:3], bh.EllipsoidalConversionType.GEODETIC
        )
        return bh.position_enz_to_azel(enz, bh.AngleFormat.DEGREES)[:2]

    sats, radii_km = [], []
    for sat in sp3.satellites():
        if not sat.get_name().startswith("G"):
            continue
        az, el = azel(sat, EPOCH)
        track = [azel(sat, EPOCH + dt) for dt in TRACK_OFFSETS_S]
        sats.append(
            {
                "prn": int(sat.get_name()[1:]),
                "az_deg": float(az),
                "el_deg": float(el),
                "visible": bool(el >= EL_MASK_DEG),
                "track_azel_deg": [[round(float(a), 3), round(float(e), 3)] for a, e in track if e >= 0.0],
            }
        )
        radii_km.append(np.linalg.norm(sat.state_ecef(EPOCH)[:3]) / 1e3)

    n_visible = sum(s["visible"] for s in sats)

    assert 24 <= len(sats) <= 34, f"{len(sats)} GPS satellites"
    assert 6 <= n_visible <= 14, f"{n_visible} visible satellites"
    assert all(-90.0 <= s["el_deg"] <= 90.0 for s in sats), "elevation out of range"
    assert all(26_000.0 <= r <= 27_200.0 for r in radii_km), "satellite radius out of range"

    result = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "epoch_utc": "2026-11-12T19:00:00Z",
        "product": product.name,
        "station": STANFORD,
        "el_mask_deg": EL_MASK_DEG,
        "sats": sorted(sats, key=lambda s: s["prn"]),
        "n_visible": n_visible,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, separators=(",", ":")))

    visible = sorted(s["prn"] for s in sats if s["visible"])
    print(f"product {product.name}")
    print(f"{len(sats)} GPS satellites, {n_visible} above {EL_MASK_DEG:.0f} deg at {result['epoch_utc']}")
    print("visible PRNs:", " ".join(f"G{p:02d}" for p in visible))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
