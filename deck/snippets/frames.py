# /// script
# requires-python = ">=3.12"
# dependencies = ["brahe @ git+https://github.com/duncaneddy/brahe@3e2ed7c1739b3f372c35c708702246bbee831183", "numpy"]
# ///

import brahe as bh
import numpy as np

bh.initialize_eop()
epoch = bh.Epoch(2026, 11, 12, 19, 0, 0.0, time_system=bh.UTC)
NAME = "IGS0OPSULT_20263150000_02D_15M_ORB.SP3.gz"

igs = bh.IGSProductsClient("BKG")
product = {p.name: p for p in igs.list_products(epoch)}[NAME]
sp3 = igs.download_sp3(product)
sat = next(s for s in sp3.satellites() if s.get_name() == "G01")

epochs = [epoch - 86400.0 + t for t in range(0, 86401, 300)]
r_gcrf = np.array(sat.states_gcrf(epochs))[:, :3] / 1e3
r_itrf = np.array(sat.states_itrf(epochs))[:, :3] / 1e3
gap = np.linalg.norm(r_gcrf - r_itrf, axis=1).max()
print(f"G01: GCRF and ITRF differ by up to {gap:.0f} km")
