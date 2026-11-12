# /// script
# requires-python = ">=3.12"
# dependencies = ["brahe @ git+https://github.com/duncaneddy/brahe@3e2ed7c1739b3f372c35c708702246bbee831183", "numpy"]
# ///

import brahe as bh
import numpy as np

lla = [-122.1697, 37.4275, 30.0]  # Stanford lon, lat, alt
correct = bh.Epoch(2026, 11, 12, 19, 0, 0.0, time_system=bh.GPS)
mistaken = bh.Epoch(2026, 11, 12, 19, 0, 0.0, time_system=bh.UTC)

igs = bh.IGSProductsClient("BKG")
ultra_rapid = igs.list_products_between(
    correct, correct, center="IGS", solution="ULT", content="ORB"
)
sp3 = igs.download_sp3(ultra_rapid[-1])  # latest issue
sat = next(s for s in sp3.satellites() if s.get_name() == "G09")
site = bh.position_geodetic_to_ecef(lla, bh.AngleFormat.DEGREES)

error_km = []
for dt in range(-13620, 12901, 30):
    good = np.linalg.norm(sat.state_ecef(correct + dt)[:3] - site)
    bad = np.linalg.norm(sat.state_ecef(mistaken + dt)[:3] - site)
    error_km.append((bad - good) / 1e3)
shift = sat.state_ecef(mistaken)[:3] - sat.state_ecef(correct)[:3]
shift_km = np.linalg.norm(shift) / 1e3
max_km = np.abs(error_km).max()
print(f"error: position {shift_km:.1f} km, range {max_km:.1f} km")
