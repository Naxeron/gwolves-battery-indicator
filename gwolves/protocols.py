import time

# G-Wolves USB Vendor ID (Universal for all G-Wolves devices)
VID = 0x33e4

# Database of all known G-Wolves models and their protocols
MODELS = {
    # New Protocol (IsNewProtocol = "1")
    0x3808: ("HTM Plus (Wired)", "new"),
    0x3817: ("HTM Plus (Wireless)", "new"),
    0x6808: ("HSK Pro 2.0 (Wired)", "new"),
    0x6817: ("HSK Pro 2.0 (Wireless)", "new"),
    0x5608: ("HTXU (Wired)", "new"),
    0x5617: ("HTXU (Wireless)", "new"),
    0x3608: ("Fenrir Pro (Wired)", "new"),
    0x3617: ("Fenrir Pro (Wireless)", "new"),
    0x5418: ("HTS Plus (Wired, 3950)", "new"),
    0x3854: ("Receiver (Wireless, 3950/3955)", "new"),
    0x4718: ("Lycan (Wired, 3950)", "new"),
    0x5618: ("HTXU (Wired, 3950)", "new"),
    0x4719: ("Lycan (Wired, 3955)", "new"),
    0x5619: ("HTXU (Wired, 3955)", "new"),
    0x5419: ("HTS Plus (Wired, 3955)", "new"),
    0x3619: ("Fenrir Pro (Wired, 3955)", "new"),
    0x2719: ("HTX Mini (Wired, 3955)", "new"),
    0x5807: ("HSK Pro 4K (Wireless)", "new"), # Added for HSK Pro 4K

    # Old Protocol (IsNewProtocol = "0")
    0x3908: ("VUK (Wired)", "old"),
    0x3917: ("VUK (Wireless)", "old"),
    0x7904: ("HT-S2 (Wired)", "old"),
    0x7913: ("HT-S2 (Wireless)", "old"),
    0x3708: ("Fenir Max (Wired)", "old"),
    0x3717: ("Fenir Max (Wireless)", "old"),
    0x5308: ("HTS Ultra (Wired)", "old"),
    0x5317: ("HTS Ultra (Wireless)", "old"),
    0x7704: ("HTR (Wired)", "old"),
    0x7713: ("HTR (Wireless)", "old"),
    0x3508: ("Fenrir (Wired)", "old"),
    0x3517: ("Fenrir (Wireless)", "old"),
    0x7908: ("HT-S2 Pro (Wired)", "old"),
    0x7917: ("HT-S2 Pro (Wireless)", "old"),
    0x5808: ("HSK Pro (Wired)", "old"),
    0x5817: ("HSK Pro (Wireless)", "old"),
    0x2708: ("HTX Mini (Wired)", "old"),
    0x2717: ("HTX Mini (Wireless)", "old"),
    0x5408: ("HTS Plus (Wired)", "old"),
    0x5417: ("HTS Plus (Wireless)", "old"),
    0x5708: ("HTX (Wired)", "old"),
    0x5717: ("HTX (Wireless)", "old"),
    0x5908: ("HSK Plus (Wired)", "old"),
    0x5917: ("HSK Plus (Wireless)", "old"),
    0x7204: ("HSK Lite (Wired)", "old"),
    0x7203: ("HSK Lite (Wireless)", "old"),
    0x7708: ("HTR Pro (Wired)", "old"),
    0x7717: ("HTR Pro (Wireless)", "old"),
    0x5804: ("HSK Pro ACE (Wired)", "old"),
    0x5803: ("HSK Pro ACE (Wireless)", "old"),
    0x5404: ("HTS Plus ACE (Wired)", "old"),
    0x5403: ("HTS Plus ACE (Wireless)", "old"),
    0x5704: ("HTX ACE (Wired)", "old"),
    0x5703: ("HTX ACE (Wireless)", "old"),
    0x5904: ("HSK Plus ACE (Wired)", "old"),
    0x5903: ("HSK Plus ACE (Wireless)", "old"),
}

# Cache for dynamically detected/probed models: PID -> (model_name, protocol)
DYNAMIC_PROTOCOLS = {}

# Mappings for New/Old Protocols: Frequency (Hz) -> Byte Value
FREQ_TO_BYTE_NEW = {
    125: 8,
    250: 4,
    500: 2,
    1000: 1,
    2000: 32,
    4000: 64,
    8000: 128
}

BYTE_TO_FREQ_NEW = {v: k for k, v in FREQ_TO_BYTE_NEW.items()}
# Normalize 16 to 1000Hz (since some devices use/return 16 for 1000Hz)
BYTE_TO_FREQ_NEW[16] = 1000


def query_polling_rate(dev, protocol, is_wireless, is_high_rate=False):
    """Queries the current polling rate of the G-Wolves device."""
    try:
        if protocol == "new":
            buf = [0] * 65
            buf[0] = 0
            buf[3] = 2
            buf[4] = 2
            buf[5] = 1
            buf[6] = 0x80
            buf[7] = 1 if is_wireless else 2
            
            dev.send_feature_report(buf)
            time.sleep(0.05)
            resp = dev.get_feature_report(0, 65)
            if not resp or len(resp) < 10:
                return None
            
            payload = resp[1:]
            # Unshifted
            if payload[0] == 161 and payload[3] == 2 and payload[5] == 128:
                byte_val = payload[7]
            # Shifted
            elif payload[1] == 161 and payload[4] == 2 and payload[6] == 128:
                byte_val = payload[8]
            else:
                return None
            
            if byte_val == 16:
                byte_val = 1
            return BYTE_TO_FREQ_NEW.get(byte_val, 1000)
            
        elif protocol == "old":
            buf = [0] * 65
            buf[0] = 0
            buf[2] = 2
            buf[3] = 0x82
            
            dev.send_feature_report(buf)
            time.sleep(0.05)
            resp = dev.get_feature_report(0, 65)
            if not resp or len(resp) < 8:
                return None
                
            payload = resp[1:]
            # Unshifted
            if payload[0] == 161 and payload[1] == 2 and payload[2] == 0x82:
                byte_val = payload[4]
            # Shifted
            elif payload[1] == 161 and payload[2] == 2 and payload[3] == 0x82:
                byte_val = payload[5]
            else:
                return None
                
            if byte_val == 16:
                byte_val = 1
            return BYTE_TO_FREQ_NEW.get(byte_val, 1000)
            
    except Exception as e:
        print(f"Error querying polling rate: {e}")
    return None


def set_polling_rate(dev, protocol, is_wireless, freq, is_high_rate=False):
    """Sets the G-Wolves device polling rate."""
    try:
        if protocol == "new":
            byte_val = FREQ_TO_BYTE_NEW.get(freq)
            if not byte_val:
                return False
            buf = [0] * 65
            buf[0] = 0
            buf[3] = 2
            buf[4] = 2
            buf[5] = 1
            buf[6] = 0
            buf[7] = 1 if is_wireless else 2
            buf[8] = byte_val
            
            dev.send_feature_report(buf)
            time.sleep(0.05)
            return True
            
        elif protocol == "old":
            byte_val = FREQ_TO_BYTE_NEW.get(freq)
            if not byte_val:
                return False
            buf = [0] * 65
            buf[0] = 0
            buf[2] = 2
            buf[3] = 2
            buf[4] = 0
            buf[5] = byte_val
            
            dev.send_feature_report(buf)
            time.sleep(0.05)
            return True
            
    except Exception as e:
        print(f"Error setting polling rate: {e}")
    return False


def query_battery(dev, protocol, is_wireless):
    """Sends battery status request and parses responses based on protocol type."""
    try:
        if protocol == "new":
            buf = [0] * 65
            buf[0] = 0
            buf[3] = 2     # wiredMouseDeviceID (typically 2)
            buf[4] = 2     # Command Category
            buf[6] = 0x83  # Command ID: Get Battery
            
            dev.send_feature_report(buf)
            time.sleep(0.1)
            resp = dev.get_feature_report(0, 65)
            if not resp or len(resp) < 10:
                return False, 0, False, "No response"
            
            payload = resp[1:]
            # Case A: Shifted Response
            if payload[1] == 161 and payload[4] == 2 and payload[6] == 131:
                return True, payload[8], (payload[7] == 1), ""
            # Case B: Unshifted Response
            elif payload[0] == 161 and payload[3] == 2 and payload[5] == 131:
                return True, payload[7], (payload[6] == 1), ""
            
        elif protocol == "old":
            buf = [0] * 65
            buf[0] = 0
            buf[2] = 2     # Command Category
            buf[3] = 0x8F  # Command ID: Get Battery
            buf[4] = 1 if is_wireless else 0
            
            dev.send_feature_report(buf)
            time.sleep(0.1)
            resp = dev.get_feature_report(0, 65)
            if not resp or len(resp) < 10:
                return False, 0, False, "No response"
            
            payload = resp[1:]
            # Case A: Shifted Response
            if payload[1] == 161 and payload[2] == 2 and payload[3] == 0x8F:
                return True, payload[6], (payload[5] == 1), ""
            # Case B: Unshifted Response
            elif payload[0] == 161 and payload[1] == 2 and payload[2] == 0x8F:
                return True, payload[5], (payload[4] == 1), ""
                
        elif protocol == "compx":
            buf = [0] * 17
            buf[0] = 0
            buf[1] = 0x04  # Command ID
            
            dev.send_feature_report(buf)
            time.sleep(0.1)
            resp = dev.get_feature_report(0, 17)
            if not resp or len(resp) < 10:
                return False, 0, False, "No response"
            
            payload = resp[1:]
            percentage = payload[5]
            is_charging = (payload[6] == 1)
            if 0 <= percentage <= 100:
                return True, percentage, is_charging, ""
                
    except Exception as e:
        return False, 0, False, str(e)
    return False, 0, False, "Protocol mismatch"
