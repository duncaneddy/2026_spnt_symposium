# /// script
# requires-python = ">=3.12"
# dependencies = ["brahe @ git+https://github.com/duncaneddy/brahe@3e2ed7c1739b3f372c35c708702246bbee831183", "numpy"]
# ///

import brahe as bh
import numpy as np

bh.initialize_eop()
epc = bh.Epoch(2026, 11, 12, 19, 0, 0.0, time_system=bh.UTC)
oe = np.array([bh.R_EARTH + 20_200e3, 0.0, 55.0, 0.0, 0.0, 0.0])
x0 = bh.state_koe_to_eci(oe, bh.AngleFormat.DEGREES)
x = np.tile(x0, (100_000, 1))  # 100,000 states
x_itrf = bh.state_gcrf_to_itrf(epc, x)
F = bh.CelestialFrame
x_teme = bh.state_frame_to_frame(F.GCRF, F.TEME, epc, x)
print(x_itrf.shape, x_teme.shape)
