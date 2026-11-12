# /// script
# requires-python = ">=3.12"
# dependencies = ["brahe @ git+https://github.com/duncaneddy/brahe@3e2ed7c1739b3f372c35c708702246bbee831183", "numpy"]
# ///

import brahe as bh
import numpy as np

bh.initialize_eop()
bh.initialize_sw()
DEG = bh.AngleFormat.DEGREES
t0 = bh.Epoch(2026, 11, 12, 19, 0, 0.0, time_system=bh.UTC)
a = bh.R_EARTH + 500e3
inc = bh.sun_synchronous_inclination(a, 0.0, angle_format=DEG)
x0 = bh.state_koe_to_eci(np.array([a, 0, inc, 0, 0, 0]), DEG)
params = np.array([100, 1, 2.2, 1, 1.3])  # kg, m2, Cd, m2, Cr
cfg = bh.NumericalPropagationConfig.default()

full = bh.ForceModelConfig.default()
no_drag = bh.ForceModelConfig.default()
no_drag.drag = None

r = []
for force in (bh.ForceModelConfig.two_body(), full, no_drag):
    prop = bh.NumericalOrbitPropagator(t0, x0, cfg, force, params)
    prop.propagate_to(t0 + 3 * 86400.0)
    r.append(prop.current_state()[:3] / 1e3)
dr = np.linalg.norm(r[1] - r[0])
dr_drag = np.linalg.norm(r[1] - r[2])
print(f"full vs two-body {dr:.0f} km, drag alone {dr_drag:.1f} km")
