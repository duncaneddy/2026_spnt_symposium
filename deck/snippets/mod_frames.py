# /// script
# requires-python = ">=3.12"
# dependencies = ["brahe @ git+https://github.com/duncaneddy/brahe@3e2ed7c1739b3f372c35c708702246bbee831183", "numpy"]
# ///

import brahe as bh
import numpy as np

bh.initialize_eop()
epc = bh.Epoch(2026, 11, 12, 19, 0, 0.0, time_system=bh.UTC)
oe = np.zeros((100_000, 6))
oe[:, 0], oe[:, 2] = bh.R_EARTH + 20_200e3, 55.0
oe[:, 5] = np.linspace(0.0, 360.0, 100_000)
x = bh.state_koe_to_eci(oe, bh.AngleFormat.DEGREES)
x_itrf = bh.state_gcrf_to_itrf(epc, x)
F = bh.CelestialFrame
x_teme = bh.state_frame_to_frame(F.GCRF, F.TEME, epc, x)
print(x_itrf.shape, x_teme.shape)
