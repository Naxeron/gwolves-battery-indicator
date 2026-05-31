import hid
import app
import time

dev = hid.device()
devices = hid.enumerate(0x33e4, 0x5807)
dev.open_path(devices[0]['path'])

print("Setting to 500 using NEW...")
app.set_polling_rate(dev, "new", True, 500)
time.sleep(0.5)

print("NEW poll:", app.query_polling_rate(dev, "new", True))
print("OLD poll:", app.query_polling_rate(dev, "old", True))

print("Setting back to 1000 using NEW...")
app.set_polling_rate(dev, "new", True, 1000)

dev.close()
