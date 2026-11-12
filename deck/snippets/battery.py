# /// script
# requires-python = ">=3.12"
# dependencies = ["brahe @ git+https://github.com/duncaneddy/brahe@3e2ed7c1739b3f372c35c708702246bbee831183", "numpy"]
# ///

import brahe as bh
import numpy as np

bh.initialize_eop()
epoch = bh.Epoch(2024, 6, 21, 12, 0, 0.0, time_system=bh.UTC)
oe = np.array([bh.R_EARTH + 500e3, 0.01, 45.0, 15.0, 30.0, 45.0])
orbit = bh.state_koe_to_eci(oe, bh.AngleFormat.DEGREES)
x0 = np.concatenate([orbit, [80.0]])  # battery charge, Wh


def battery(t, state, params):
    dx = np.zeros(len(state))
    sun = bh.eclipse_conical(state[:3], bh.sun_position(epoch + t))
    dx[6] = (50.0 * sun - 30.0) / 3600.0  # 50 W panels, 30 W load
    return dx


cfg = bh.NumericalPropagationConfig.default()
two_body = bh.ForceModelConfig.two_body()
prop = bh.NumericalOrbitPropagator(
    epoch, x0, cfg, two_body, additional_dynamics=battery
)
prop.propagate_to(epoch + 3 * bh.orbital_period(oe[0]))
print(f"charge after 3 orbits: {prop.current_state()[6]:.1f} Wh")
