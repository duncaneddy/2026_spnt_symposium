# /// script
# requires-python = ">=3.12"
# dependencies = ["brahe @ git+https://github.com/duncaneddy/brahe@3e2ed7c1739b3f372c35c708702246bbee831183"]
# ///

import brahe as bh

epc = bh.Epoch(2026, 11, 12, 19, 0, 0.0, time_system=bh.UTC)
a = bh.R_EARTH + 20_200e3
# 24 satellites, 6 planes, phasing 2, inclination 55 degrees
gen = bh.WalkerConstellationGenerator.builder(
    24, 6, 2, a, 55.0, epc
)
sats = gen.build().as_keplerian_propagators(60.0)
hours = bh.orbital_period(a) / 3600
print(f"{len(sats)} satellites, period {hours:.2f} h")
