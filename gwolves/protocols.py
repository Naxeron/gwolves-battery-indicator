"""HID report encoding and validated response decoding for G-Wolves mice."""

import logging
import time


logger = logging.getLogger(__name__)

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


def _send_report(dev, report):
    """Require HIDAPI to accept the complete report, including its report ID."""
    written = dev.send_feature_report(report)
    if written != len(report):
        raise OSError(f"Incomplete feature report write ({written} of {len(report)} bytes)")


def _matching_payload(response, protocol, command, minimum_length, category=2):
    """Normalize the two documented reply offsets only after header validation."""
    if not response or response[0] != 0:
        return None
    for offset in (1, 2):
        payload = response[offset:]
        if len(payload) < minimum_length or payload[0] != 0xA1:
            continue
        if protocol == "new":
            matches = payload[3] == category and payload[5] == command
        else:
            matches = payload[1] == category and payload[2] == command
        if matches:
            return payload
    return None


def _query_active_profile(dev):
    """Read the profile selector required by new-protocol performance commands."""
    buf = [0] * 65
    buf[3:7] = [2, 1, 0, 0x85]
    _send_report(dev, buf)
    time.sleep(0.05)
    response = dev.get_feature_report(0, 65)
    payload = _matching_payload(response, "new", 0x85, 7, category=1)
    if payload is None:
        return None
    profile = payload[6]
    # The reference uses one-based profile IDs but supplies no per-model maximum.
    return profile if isinstance(profile, int) and 1 <= profile <= 255 else None


def query_polling_rate(dev, protocol, is_wireless, is_high_rate=False):
    """Return the reported rate in Hz, or None for an unrecognized/failed reply."""
    buf = [0] * 65
    try:
        if protocol == "new":
            profile = _query_active_profile(dev)
            if profile is None:
                return None
            buf[3:8] = [2, 2, 1, 0x80, profile]
            command, minimum_length, value_index = 0x80, 8, 7
        elif protocol == "old":
            buf[2:5] = [2, 0x82, 1 if is_wireless else 0]
            command, minimum_length, value_index = 0x82, 5, 4
        else:
            return None
        _send_report(dev, buf)
        time.sleep(0.05)
        response = dev.get_feature_report(0, 65)
    except OSError as exc:
        logger.debug("Polling rate query failed (%s): %s", protocol, exc)
        return None

    payload = _matching_payload(response, protocol, command, minimum_length)
    if payload is None:
        return None
    if protocol == "new" and (payload[4] != 1 or payload[6] != profile):
        return None
    return BYTE_TO_FREQ_NEW.get(payload[value_index])


def set_polling_rate(dev, protocol, is_wireless, freq, is_high_rate=False):
    """Send a rate change; True means a complete write, not device confirmation.

    New-protocol changes target the device's active profile. If that cannot be
    read, no setting is written. Query the rate afterward to verify application.
    """
    byte_val = FREQ_TO_BYTE_NEW.get(freq)
    if byte_val is None:
        return False
    buf = [0] * 65
    try:
        if protocol == "new":
            profile = _query_active_profile(dev)
            if profile is None:
                logger.warning("Polling rate change skipped: active profile is unavailable")
                return False
            buf[3:9] = [2, 2, 1, 0, profile, byte_val]
        elif protocol == "old":
            buf[2:6] = [2, 2, 1 if is_wireless else 0, byte_val]
        else:
            return False
        _send_report(dev, buf)
        time.sleep(0.05)
    except OSError as exc:
        logger.warning("Polling rate change failed (%s): %s", protocol, exc)
        return False
    return True


def query_battery(dev, protocol, is_wireless):
    """Return (success, percentage, charging, error) from a validated reply."""
    if protocol == "new":
        buf = [0] * 65
        buf[3:7] = [2, 2, 0, 0x83]
        command, minimum_length, percentage_index, charging_index = 0x83, 8, 7, 6
    elif protocol == "old":
        buf = [0] * 65
        buf[2:5] = [2, 0x8F, 1 if is_wireless else 0]
        command, minimum_length, percentage_index, charging_index = 0x8F, 6, 5, 4
    elif protocol == "compx":
        # Retained for explicitly selected legacy devices; transport is experimental.
        buf = [0] * 17
        buf[1] = 4
        percentage_index, charging_index = 5, 6
    else:
        return False, 0, False, "Unsupported protocol"

    try:
        _send_report(dev, buf)
        time.sleep(0.1)
        response = dev.get_feature_report(0, len(buf))
    except OSError as exc:
        logger.debug("Battery query failed (%s): %s", protocol, exc)
        return False, 0, False, str(exc)

    if not response:
        return False, 0, False, "No response"
    if protocol == "compx":
        # The reference driver's retrySetGetWithDelayCompx checks 16 payload bytes
        # and an echoed command. A plausible percentage alone is not a reply.
        if len(response) != 17 or response[0] != 0 or response[1] != 4:
            return False, 0, False, "Protocol mismatch"
        payload = response[1:]
    else:
        payload = _matching_payload(response, protocol, command, minimum_length)
        if payload is None:
            return False, 0, False, "Protocol mismatch"

    percentage, charging = payload[percentage_index], payload[charging_index]
    if not 0 <= percentage <= 100:
        return False, 0, False, "Invalid battery percentage"
    if charging not in (0, 1):
        return False, 0, False, "Invalid charging flag"
    return True, percentage, charging == 1, ""
