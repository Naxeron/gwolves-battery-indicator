import hid
import time

VID = 0x33e4
# Let's search for any G-Wolves device interface
devices = hid.enumerate(VID)

if not devices:
    print("No G-Wolves devices found.")
    exit(1)

for d in devices:
    print(f"Path: {d['path']}, Product: {d['product_string']}, Interface: {d['interface_number']}")
    try:
        dev = hid.device()
        dev.open_path(d['path'])
        
        # We try to send getPollingRate for both new and old protocol
        # New protocol getPollingRate (t=1):
        # o[2]=2, o[3]=2, o[4]=1, o[5]=128 (0x80), o[6]=t (1 or 2)
        # In python-hidapi:
        # buf[0] = 0
        # buf[3] = 2
        # buf[4] = 2
        # buf[5] = 1
        # buf[6] = 128 (0x80)
        # buf[7] = 1 (or 2)
        for t in [1, 2]:
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
            if resp and len(resp) > 8:
                payload = resp[1:]
                # let's print raw response
                print(f"  t={t} New Protocol Response: {list(resp[:12])}")
                
        # Old protocol getPollRate:
        # buf[2] = 2, buf[3] = 130 (0x82)
        buf = [0] * 65
        buf[0] = 0
        buf[2] = 2
        buf[3] = 0x82
        dev.send_feature_report(buf)
        time.sleep(0.05)
        resp = dev.get_feature_report(0, 65)
        if resp and len(resp) > 6:
            print(f"  Old Protocol Response: {list(resp[:10])}")
            
        dev.close()
    except Exception as e:
        print(f"  Failed: {e}")
