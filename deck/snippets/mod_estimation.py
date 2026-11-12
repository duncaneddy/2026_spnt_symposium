# /// script
# requires-python = ">=3.12"
# dependencies = ["brahe @ git+https://github.com/duncaneddy/brahe@3e2ed7c1739b3f372c35c708702246bbee831183", "numpy"]
# ///

import brahe as bh
import numpy as np

bh.initialize_eop()
epc = bh.Epoch(2026, 11, 12, 19, 0, 0.0, time_system=bh.UTC)
x0 = np.array([6878e3, 0.0, 0.0, 0.0, 4728.0, 5965.0])  # m, m/s
orbit = bh.KeplerianPropagator.from_eci(epc, x0, 60.0)
ekf = bh.ExtendedKalmanFilter(
    epc,
    x0,
    np.diag([1e6] * 3 + [1e2] * 3),
    measurement_models=[bh.InertialPositionMeasurementModel(5.0)],
    propagation_config=bh.NumericalPropagationConfig.default(),
    force_config=bh.ForceModelConfig.two_body(),
)
for t in [epc + 60.0 * k for k in range(1, 31)]:
    fix = bh.Observation(t, orbit.state_eci(t)[:3], model_index=0)
    ekf.process_observation(fix)
print(len(ekf.records()), "observations processed")
