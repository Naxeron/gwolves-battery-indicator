import hid
import time

VID = 0x33e4
PID = 0x3617

print(f"Searching for G-Wolves device VID: {hex(VID)}, PID: {hex(PID)}...")
devices = hid.enumerate(VID, PID)

if not devices:
    print("No devices found. Is the receiver plugged in?")
    exit(1)

print(f"Found {len(devices)} device interfaces:")
for d in devices:
    print(f"Path: {d['path']}")
    print(f"  Interface: {d['interface_number']}")
    print(f"  Product: {d['product_string']}")
    
for d in devices:
    print(f"\n--- Trying to open interface {d['interface_number']} ---")
    try:
        dev = hid.device()
        dev.open_path(d['path'])
        print("Successfully opened device!")
        
        # Prepare battery command for New Protocol (IsNewProtocol == "1")
        # JS: r[2] = 2, r[3] = 2, r[5] = 131 (0x83)
        # Note: python-hidapi send_feature_report needs Report ID (0) as the first byte
        buf = [0] * 65 # 1 byte report ID + 64 bytes payload
        buf[0] = 0     # Report ID
        buf[3] = 2     # r[2] in payload
        buf[4] = 2     # r[3] in payload
        buf[6] = 0x83  # r[5] in payload (0x83)
        
        print(f"Sending feature report: {buf[:10]}...")
        dev.send_feature_report(buf)
        
        time.sleep(0.1)
        
        print("Reading feature report response...")
        resp = dev.get_feature_report(0, 65)
        print(f"Response: {list(resp)}")
        
        # Parse response payload (skip first byte which is report ID)
        payload = resp[1:]
        
        # Case A (shifted by 1 byte)
        if payload[1] == 161 and payload[4] == 2 and payload[6] == 131:
            charge = payload[7]
            level = payload[8]
            print(f"parsed (Case A): Battery: {level}%, Charging: {charge == 1}")
        # Case B (unshifted)
        elif payload[0] == 161 and payload[3] == 2 and payload[5] == 131:
            charge = payload[6]
            level = payload[7]
            print(f"parsed (Case B): Battery: {level}%, Charging: {charge == 1}")
        else:
            print("Response did not match expected battery patterns.")
            
        dev.close()
    except Exception as e:
        print(f"Failed: {e}")
