# /// script
# requires-python = ">=3.12"
# dependencies = ["brahe @ git+https://github.com/duncaneddy/brahe@3e2ed7c1739b3f372c35c708702246bbee831183", "numpy"]
# ///

import brahe as bh
import numpy as np

bh.initialize_eop()
epc = bh.Epoch(2026, 11, 12, 19, 0, 0.0, time_system=bh.UTC)

# One satellite at GPS altitude
oe = np.array([bh.R_EARTH + 20_200e3, 0.0, 55.0, 0.0, 0.0, 0.0])
sat = bh.KeplerianPropagator.from_keplerian(
    epc, oe, bh.AngleFormat.DEGREES, 60.0
)

# Every KSAT ground station, with a 10 degree elevation mask
stations = bh.datasets.groundstations.load("ksat")
mask = bh.ElevationConstraint(min_elevation_deg=10.0)

# All access windows over one day
windows = bh.location_accesses(
    stations, sat, epc, epc + 86400.0, mask
)

print(len(stations), "stations,", len(windows), "access windows")
