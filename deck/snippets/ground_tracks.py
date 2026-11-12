# /// script
# requires-python = ">=3.12"
# dependencies = ["brahe @ git+https://github.com/duncaneddy/brahe@3e2ed7c1739b3f372c35c708702246bbee831183", "numpy"]
# ///

import brahe as bh
import numpy as np

bh.initialize_eop()
DEG = bh.AngleFormat.DEGREES
epoch = bh.Epoch(2026, 11, 12, 19, 0, 0.0, time_system=bh.UTC)
epochs = [epoch + t for t in range(0, 12 * 3600 + 1, 120)]

celestrak = bh.celestrak.CelestrakClient()
records = celestrak.get_gp(group="gps-ops")

tracks = {}
for rec in records:
    sat = rec.to_sgp_propagator(120.0)
    itrf = np.array(sat.states_itrf(epochs))[:, :3]
    geod = [bh.position_ecef_to_geodetic(r, DEG) for r in itrf]
    tracks[rec.object_name] = np.array(geod)[:, :2]  # lon, lat
print(len(tracks), "GPS ground tracks of", len(epochs), "points")
