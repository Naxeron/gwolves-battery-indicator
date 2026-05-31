import hid
import app
dev = hid.device()
# find path
devices = hid.enumerate(0x33e4, 0x5807)
if not devices:
    print("No device")
    exit()
dev.open_path(devices[0]['path'])
print("NEW:", app.query_battery(dev, "new", True))
print("OLD:", app.query_battery(dev, "old", True))
print("COMPX:", app.query_battery(dev, "compx", True))
dev.close()
