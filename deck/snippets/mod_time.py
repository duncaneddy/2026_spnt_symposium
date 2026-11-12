# /// script
# requires-python = ">=3.12"
# dependencies = ["brahe @ git+https://github.com/duncaneddy/brahe@3e2ed7c1739b3f372c35c708702246bbee831183"]
# ///

import brahe as bh

bh.initialize_eop()

# One instant, defined in UTC
epc = bh.Epoch(2026, 11, 12, 19, 0, 0.0, time_system=bh.UTC)

# The same instant in four other time scales
for ts in (bh.GPS, bh.TAI, bh.TT, bh.UT1):
    print(epc.to_time_system(ts))
