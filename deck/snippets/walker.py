# /// script
# requires-python = ">=3.12"
# dependencies = ["brahe @ git+https://github.com/duncaneddy/brahe@3e2ed7c1739b3f372c35c708702246bbee831183"]
# ///

import time
import brahe as bh

bh.initialize_eop()
bh.initialize_sw()
t0 = bh.Epoch(2026, 11, 12, 19, 0, 0.0, time_system=bh.UTC)
walker = bh.WalkerConstellationGenerator.builder(
    192, 12, 1, bh.R_EARTH + 1080e3, 53.0, t0
).build()
t_end = t0 + bh.orbital_period(walker.semi_major_axis)
rkf78 = bh.IntegrationMethod.RKF78
cfg = bh.NumericalPropagationConfig.with_method(rkf78)
cfg = cfg.with_abs_tol(1e-6).with_rel_tol(1e-12)
force = bh.ForceModelConfig.default()
params = [100, 1, 2.2, 1, 1.3]  # kg, m2, Cd, m2, Cr

serial = walker.as_numerical_propagators(cfg, force, params)
props = walker.as_numerical_propagators(cfg, force, params)
t1 = time.perf_counter()
for prop in serial:
    prop.propagate_to(t_end)
t2 = time.perf_counter()
bh.par_propagate_to(props, t_end)
t3 = time.perf_counter()
print(f"serial {t2 - t1:.2f} s, parallel {t3 - t2:.2f} s")
