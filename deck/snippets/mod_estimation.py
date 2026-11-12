# /// script
# requires-python = ">=3.12"
# dependencies = ["brahe @ git+https://github.com/duncaneddy/brahe@3e2ed7c1739b3f372c35c708702246bbee831183", "numpy"]
# ///

import brahe as bh
import numpy as np

bh.initialize_eop()
epc = bh.Epoch(2026, 11, 12, 19, 0, 0.0, time_system=bh.UTC)
oe = np.array([bh.R_EARTH + 500e3, 0.001, 51.6, 0.0, 0.0, 0.0])
DEG = bh.AngleFormat.DEGREES
truth = bh.KeplerianPropagator.from_keplerian(epc, oe, DEG, 60.0)
ekf = bh.ExtendedKalmanFilter(
    epc,
    truth.state_eci(epc) + [1e3, 0, 0, 0, 1, 0],
    np.diag([1e6] * 3 + [1e2] * 3),
    measurement_models=[bh.ECEFPositionMeasurementModel(5.0)],
    propagation_config=bh.NumericalPropagationConfig.default(),
    force_config=bh.ForceModelConfig.two_body(),
)
rng = np.random.default_rng(1)
for t in [epc + 60.0 * k for k in range(1, 31)]:
    r = bh.position_eci_to_ecef(t, truth.state_eci(t)[:3])
    fix = r + rng.normal(0.0, 5.0, 3)
    ekf.process_observation(bh.Observation(t, fix, model_index=0))
x_true = truth.state_eci(ekf.current_epoch())
err = np.linalg.norm(ekf.current_state()[:3] - x_true[:3])
print(f"30 fixes with 5 m noise: position error {err:.1f} m")
