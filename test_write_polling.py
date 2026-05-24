import hid
import time

VID = 0x33e4
PID = 0x3617 # Receiver PID

# Open the receiver (Interface 0)
devs = hid.enumerate(VID, PID)
target_dev = None
for d in devs:
    if d['interface_number'] == 0:
        target_dev = d
        break

if not target_dev:
    print("Receiver Interface 0 not found.")
    exit(1)

dev = hid.device()
dev.open_path(target_dev['path'])
print(f"Opened receiver on path: {target_dev['path']}")

# Let's define the set rate function
def set_rate(t, r):
    # o[2]=2, o[3]=2, o[4]=1, o[5]=0, o[6]=t, o[7]=r
    buf = [0] * 65
    buf[0] = 0
    buf[3] = 2
    buf[4] = 2
    buf[5] = 1
    buf[6] = 0
    buf[7] = t
    buf[8] = r
    dev.send_feature_report(buf)
    time.sleep(0.05)

def get_rate(t):
    # o[2]=2, o[3]=2, o[4]=1, o[5]=128, o[6]=t
    buf = [0] * 65
    buf[0] = 0
    buf[3] = 2
    buf[4] = 2
    buf[5] = 1
    buf[6] = 0x80
    buf[7] = t
    dev.send_feature_report(buf)
    time.sleep(0.05)
    resp = dev.get_feature_report(0, 65)
    return list(resp[:12]) if resp else None

# First, read initial rates
print("Initial rate t=1 (Wireless):", get_rate(1))
print("Initial rate t=2 (Wired):", get_rate(2))

# Test values of r (0, 1, 2, 3, 4, 5, 6, 7, 8, 16, 128)
test_values = [1, 2, 4, 8, 16, 128]
print("\nTesting wireless (t=1) values:")
for val in test_values:
    set_rate(1, val)
    resp = get_rate(1)
    # The return byte we expect is in resp[8] (corresponding to payload[7] in JS unshifted)
    # Wait, in get_rate response payload:
    # resp = [0, 161, 0, 2, 2, 1, 128, 1, byte_val, ...]
    # So resp[8] is the value!
    print(f"  Sent: {val} -> Received: {resp[8]} (Full response: {resp})")

# Let's restore a safe default value, e.g. 1000Hz (which is usually index/value 1 or 8 or 128? We will see!)
# Wait, let's restore whatever was the initial wireless rate
initial_val = get_rate(1)[8]
set_rate(1, initial_val)
print(f"\nRestored wireless rate to: {initial_val}")

dev.close()
