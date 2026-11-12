# /// script
# requires-python = ">=3.12"
# dependencies = ["brahe @ git+https://github.com/duncaneddy/brahe@3e2ed7c1739b3f372c35c708702246bbee831183", "numpy"]
# ///

import brahe as bh
import numpy as np

bh.initialize_eop()


class MidpointRange(bh.AccessPropertyComputer):
    def sampling_config(self):
        return bh.SamplingConfig.midpoint()

    def compute(self, window, epochs, states, site, lla):
        range_m = np.linalg.norm(states[0][:3] - site)
        return {"range_km": range_m / 1e3}

    def property_names(self):
        return ["range_km"]


t0 = bh.Epoch(2026, 11, 12, 19, 0, 0.0, time_system=bh.UTC)
t1 = t0 + 86400.0
oe = np.array([bh.R_EARTH + 500e3, 0.001, 97.4, 0, 0, 0])
DEG = bh.AngleFormat.DEGREES
sat = bh.KeplerianPropagator.from_keplerian(t0, oe, DEG, 60)
site = bh.PointLocation(-122.1697, 37.4275, 30.0)
mask = bh.ElevationConstraint(min_elevation_deg=10.0)
computers = [MidpointRange()]

windows = bh.location_accesses(
    [site], [sat], t0, t1, mask, property_computers=computers
)
props = [w.properties.additional for w in windows]
print([round(p["range_km"]) for p in props])
