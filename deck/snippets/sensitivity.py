# /// script
# requires-python = ">=3.12"
# dependencies = ["brahe @ git+https://github.com/duncaneddy/brahe@3e2ed7c1739b3f372c35c708702246bbee831183", "numpy"]
# ///

import brahe as bh
import numpy as np

bh.initialize_eop()
bh.initialize_sw()
epoch = bh.Epoch(2024, 1, 1, 12, 0, 0.0, time_system=bh.UTC)
oe = np.array([bh.R_EARTH + 400e3, 0.01, 45.0, 0.0, 0.0, 0.0])
state = bh.state_koe_to_eci(oe, bh.AngleFormat.DEGREES)
params = np.array([500, 2, 2.2, 2, 1.3])  # kg, m2, Cd, m2, Cr

cfg = bh.NumericalPropagationConfig.default().with_sensitivity()
force = bh.ForceModelConfig.default()
prop = bh.NumericalOrbitPropagator(epoch, state, cfg, force, params)
prop.propagate_to(epoch + bh.orbital_period(oe[0]))
sens = prop.sensitivity()  # d(state) / d(params), 6 x 5
dr = np.linalg.norm(sens[:3], axis=0) * 0.01 * params
print("position change (m) for a 1% parameter change:", dr.round(2))
