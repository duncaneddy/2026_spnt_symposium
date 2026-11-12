# /// script
# requires-python = ">=3.12"
# dependencies = ["brahe @ git+https://github.com/duncaneddy/brahe@3e2ed7c1739b3f372c35c708702246bbee831183"]
# ///

import brahe as bh

GEODETIC = bh.EllipsoidalConversionType.GEODETIC
epoch = bh.Epoch(2026, 11, 12, 19, 0, 0.0, time_system=bh.UTC)
lla = [-122.1697, 37.4275, 30.0]  # Stanford lon, lat, alt

igs = bh.IGSProductsClient("BKG")
ultra_rapid = igs.list_products_between(
    epoch, epoch, center="IGS", solution="ULT", content="ORB"
)
sp3 = igs.download_sp3(ultra_rapid[-1])  # latest issue
site = bh.position_geodetic_to_ecef(lla, bh.AngleFormat.DEGREES)

visible = []
for sat in sp3.satellites():
    r = sat.state_ecef(epoch)[:3]
    enz = bh.relative_position_ecef_to_enz(site, r, GEODETIC)
    _, el, _ = bh.position_enz_to_azel(enz, bh.AngleFormat.DEGREES)
    if sat.get_name().startswith("G") and el >= 10.0:
        visible.append(sat.get_name())
print(len(visible), "GPS satellites above 10 deg:", *visible)
