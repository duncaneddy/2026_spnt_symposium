# /// script
# requires-python = ">=3.12"
# dependencies = ["brahe @ git+https://github.com/duncaneddy/brahe@3e2ed7c1739b3f372c35c708702246bbee831183"]
# ///

import brahe as bh

igs = bh.IGSProductsClient("BKG")
epc = bh.Epoch(2026, 11, 1, 12, 0, 0.0, time_system=bh.GPS)

# List the IGS rapid orbit products covering the epoch
products = igs.list_products(
    epc, center="IGS", solution="RAP", content="ORB", format="SP3"
)

# Download and parse the first one
sp3 = igs.download_sp3(products[0])

print(products[0].name)
print(len(sp3.satellite_ids), "satellites")
