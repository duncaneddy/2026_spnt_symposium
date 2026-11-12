# /// script
# requires-python = ">=3.12"
# dependencies = ["brahe @ git+https://github.com/duncaneddy/brahe@3e2ed7c1739b3f372c35c708702246bbee831183", "numpy"]
# ///

import brahe as bh
import numpy as np

bh.initialize_eop()
epoch = bh.Epoch(2024, 1, 1, 12, 0, 0.0, time_system=bh.UTC)
oe = np.array([bh.R_EARTH + 500e3, 0.01, 45.0, 15.0, 30.0, 1.0])
state = bh.state_koe_to_eci(oe, bh.AngleFormat.DEGREES)
cfg = bh.NumericalPropagationConfig.default()
force = bh.ForceModelConfig.two_body()
prop = bh.NumericalOrbitPropagator(epoch, state, cfg, force)


def z_position(epoch, state):
    return state[2]


ascending_node = bh.ValueEvent(
    "Ascending node", z_position, 0.0, bh.EventDirection.INCREASING
)
prop.add_event_detector(ascending_node)
prop.propagate_to(epoch + 3 * bh.orbital_period(oe[0]))
print([str(event.window_open) for event in prop.event_log()])
