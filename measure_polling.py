import hid
import time
import threading

VID = 0x33e4
PID = 0x3617

# Enumerate interfaces
devs = hid.enumerate(VID, PID)
if not devs:
    print("Device not found.")
    exit(1)

control_path = None
input_path = None

for d in devs:
    if d['interface_number'] == 0:
        control_path = d['path']
    elif d['interface_number'] == 1:
        input_path = d['path']

if not control_path or not input_path:
    print(f"Failed to find paths. control_path: {control_path}, input_path: {input_path}")
    exit(1)

print(f"Control path: {control_path}")
print(f"Input path: {input_path}")

# Open control device
control_dev = hid.device()
control_dev.open_path(control_path)

# Function to set rate
def set_rate(r):
    buf = [0] * 65
    buf[0] = 0
    buf[3] = 2
    buf[4] = 2
    buf[5] = 1
    buf[6] = 0
    buf[7] = 1  # Wireless (t=1)
    buf[8] = r
    control_dev.send_feature_report(buf)
    time.sleep(0.1)

# Measurement variables
deltas = []
measuring = False

def read_input():
    global measuring, deltas
    input_dev = hid.device()
    try:
        input_dev.open_path(input_path)
        input_dev.set_nonblocking(False)
        last_time = None
        while True:
            # Read blocking
            data = input_dev.read(64)
            if not data:
                break
            current_time = time.perf_counter()
            if measuring:
                if last_time is not None:
                    deltas.append(current_time - last_time)
                last_time = current_time
            else:
                last_time = None
    except Exception as e:
        print(f"Input read error: {e}")
    finally:
        try:
            input_dev.close()
        except:
            pass

# Start input reader thread
thread = threading.Thread(target=read_input, daemon=True)
thread.start()

print("\nPlease move your mouse continuously for 5 seconds to test rates...")
time.sleep(1)

# Test rates
rates_to_test = [1, 2, 4, 8, 16, 32, 64, 128]
results = {}

for r in rates_to_test:
    print(f"Setting byte value {r}...")
    set_rate(r)
    time.sleep(0.2)
    
    # Measure
    deltas = []
    measuring = True
    time.sleep(0.5)  # Collect samples for 0.5s
    measuring = False
    
    if len(deltas) > 10:
        avg_delta = sum(deltas) / len(deltas)
        measured_hz = 1.0 / avg_delta if avg_delta > 0 else 0
        results[r] = measured_hz
        print(f"  Samples: {len(deltas)}, Measured: {measured_hz:.1f} Hz")
    else:
        results[r] = 0
        print(f"  Insufficient mouse movement samples (count: {len(deltas)})")

# Restore default 1000Hz or 8000Hz (128)
set_rate(128)
control_dev.close()

print("\n--- Summary ---")
for r, hz in results.items():
    print(f"Byte: {r} -> {hz:.1f} Hz")
