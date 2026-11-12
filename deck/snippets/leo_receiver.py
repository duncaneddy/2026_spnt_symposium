# /// script
# requires-python = ">=3.12"
# dependencies = ["brahe @ git+https://github.com/duncaneddy/brahe@3e2ed7c1739b3f372c35c708702246bbee831183"]
# ///

import brahe as bh

bh.initialize_eop()
DEG = bh.AngleFormat.DEGREES
GEODETIC = bh.EllipsoidalConversionType.GEODETIC
epoch = bh.Epoch(2026, 11, 12, 19, 0, 0.0, time_system=bh.UTC)
lla = [-122.1697, 37.4275, 30.0]  # Stanford lon, lat, alt
NAME = "IGS0OPSULT_20263150000_02D_15M_ORB.SP3.gz"
igs = bh.IGSProductsClient("BKG")
product = {p.name: p for p in igs.list_products(epoch)}[NAME]
sp3 = igs.download_sp3(product)
iss = bh.celestrak.CelestrakClient().get_sgp_propagator(catnr=25544)


def gps_in_view(rx):
    n = 0
    for sat in sp3.satellites():
        r = sat.state_ecef(epoch)[:3]
        enz = bh.relative_position_ecef_to_enz(rx, r, GEODETIC)
        el = bh.position_enz_to_azel(enz, DEG)[1]
        n += sat.get_name().startswith("G") and el >= 5.0
    return n


n_ground = gps_in_view(bh.position_geodetic_to_ecef(lla, DEG))
n_iss = gps_in_view(iss.state_itrf(epoch)[:3])
print(f"GPS satellites in view: ground {n_ground}, ISS {n_iss}")
