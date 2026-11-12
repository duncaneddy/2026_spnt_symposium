# /// script
# requires-python = ">=3.12"
# dependencies = ["brahe @ git+https://github.com/duncaneddy/brahe@3e2ed7c1739b3f372c35c708702246bbee831183", "numpy"]
# ///

import brahe as bh
import numpy as np

bh.initialize_eop()
epc = bh.Epoch(2026, 11, 12, 19, 0, 0.0, time_system=bh.UTC)

# Initial state at GPS altitude
oe = np.array([bh.R_EARTH + 20_200e3, 0.0, 55.0, 0.0, 0.0, 0.0])
x0 = bh.state_koe_to_eci(oe, bh.AngleFormat.DEGREES)

# Integrator settings and force model, chosen separately
cfg = bh.NumericalPropagationConfig.default().with_stm()
forces = bh.ForceModelConfig.conservative_forces()

# Propagate one day
prop = bh.NumericalOrbitPropagator(epc, x0, cfg, forces)
prop.propagate_to(epc + 86400.0)

r_km = prop.current_state()[:3] / 1e3
print("position (km):", np.round(r_km, 1))
print("STM shape:", prop.stm().shape)
