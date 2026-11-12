# /// script
# requires-python = ">=3.12"
# dependencies = ["brahe @ git+https://github.com/duncaneddy/brahe@3e2ed7c1739b3f372c35c708702246bbee831183", "numpy"]
# ///

import brahe as bh
import numpy as np

bh.initialize_eop()
epoch = bh.Epoch(2026, 11, 12, 19, 0, 0.0, time_system=bh.UTC)

igs = bh.IGSProductsClient("BKG")
ultra_rapid = igs.list_products_between(
    epoch, epoch, center="IGS", solution="ULT", content="ORB"
)
sp3 = igs.download_sp3(ultra_rapid[-1])  # latest issue
sat = next(s for s in sp3.satellites() if s.get_name() == "G09")

celestrak = bh.celestrak.CelestrakClient()
sgp = celestrak.get_sgp_propagator(catnr=40105, step_size=60.0)

epochs = [epoch + t for t in range(-16800, 16801, 300)]
x_sp3 = np.array(sat.states_gcrf(epochs))
x_sgp4 = np.array(sgp.states_gcrf(epochs))
d_rtn = bh.state_eci_to_rtn(x_sp3, x_sgp4)[:, :3] / 1e3
d = np.linalg.norm(d_rtn, axis=1)
rms = np.sqrt(np.mean(d**2))
print(f"RMS {rms:.2f} km, largest {d.max():.2f} km")
