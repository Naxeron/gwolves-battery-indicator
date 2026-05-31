import hid
import app
dev = hid.device()
devices = hid.enumerate(0x33e4, 0x5807)
dev.open_path(devices[0]['path'])
print("NEW poll:", app.query_polling_rate(dev, "new", True))
print("OLD poll:", app.query_polling_rate(dev, "old", True))
dev.close()
