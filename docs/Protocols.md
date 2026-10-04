# USB HID Protocols

The application implements two G-Wolves HID feature-report protocols, internally
named `new` and `old`, and retains an experimental `compx` battery parser.

The device registry uses Vendor ID `0x33e4`. A matching vendor ID alone does not
establish protocol or model compatibility.

## Report conventions and validation

Request arrays below include the HID report ID (`0`) as their first byte; pad
the remaining bytes with zeroes to the stated report length. Response positions
use `payload = response[1:]`, excluding the report ID. `new` and `old` support
both reply offsets found in the reference driver; the cause of the extra byte
has not been established here.

Every query requires a complete write before reading, a matching response header
and command, and enough bytes for all fields. Battery percentages must be
0–100, and charging flags must be 0 or 1. Invalid or missing data returns failure
rather than a battery reading. Unknown polling-rate bytes return `None`.

New-protocol polling commands first read the active profile and use that ID as
their selector. This selector is **not** a wired/wireless flag. If the profile
cannot be read, the operation fails without sending a polling command. Polling
replies must also echo the requested profile, preventing a reply for another
profile from confirming the rate.

`set_polling_rate` returning `True` means HIDAPI accepted the complete request.
It does not prove the device applied the setting; the caller must query the rate
afterward to confirm it. An unsupported protocol or rate never sends a write.
The legacy `is_high_rate` argument is retained for API compatibility and does not
change the packet format or establish which rates a model supports.

| Rate (Hz) | Request/reply byte |
| --- | --- |
| 125 | `0x08` |
| 250 | `0x04` |
| 500 | `0x02` |
| 1000 | `0x01` (reply also accepts `0x10`) |
| 2000 | `0x20` |
| 4000 | `0x40` |
| 8000 | `0x80` |

---

## 1. "New" Protocol

Typically found on newer mice (e.g., Fenrir Pro, HTXU, models with `IsNewProtocol = "1"`). 
This protocol utilizes long 65-byte Feature Reports.

### Getting Battery
- **Request:** `[0x00, 0x00, 0x00, 0x02, 0x02, 0x00, 0x83, ...]`
- **Response Byte Positions:**
  Both supported layouts validate the `0xA1` marker, category `2`, and command `0x83`:
  - **Shifted:** `payload[1] == 161`, Battery is at `payload[8]`, Charging flag at `payload[7] == 1`.
  - **Unshifted:** `payload[0] == 161`, Battery is at `payload[7]`, Charging flag at `payload[6] == 1`.

### Getting Polling Rate
- **First, get active profile:** `[0x00, 0x00, 0x00, 0x02, 0x01, 0x00, 0x85, ...]`
  - Validate response marker `0xA1`, category `1`, and command `0x85`.
  - Unshifted profile ID: `payload[6]`; shifted: `payload[7]`.
  - Accept nonzero byte IDs (`1–255`). The bundled driver does not specify a
    model-specific maximum; this validates the field, not profile capacity.
- **Then get its rate:** `[0x00, 0x00, 0x00, 0x02, 0x02, 0x01, 0x80, <profile_id>, ...]`
- **Response Byte Positions:** 
  The polling rate byte is mapped using a specific chart (`128` = 8000Hz, `64` = 4000Hz, `1` = 1000Hz, `2` = 500Hz, etc.).
  - **Shifted:** `payload[8]`
  - **Unshifted:** `payload[7]`
  - The preceding byte must echo the queried profile; the subcategory must be `1`.

### Setting Polling Rate
- Read the active profile using the same command above before every change.
- **Request:** `[0x00, 0x00, 0x00, 0x02, 0x02, 0x01, 0x00, <profile_id>, <freq_byte>, ...]`

---

## 2. "Old" Protocol

Typically found on older mice (e.g., HSK Pro, HTX, models with `IsNewProtocol = "0"`).
Requests use 65 bytes including the report ID.

### Getting Battery
- **Request:** `[0x00, 0x00, 0x02, 0x8F, <1 wireless / 0 wired>, ...]`
- **Response Byte Positions:**
  - **Shifted:** `payload[1] == 161`, Battery is at `payload[6]`, Charging flag at `payload[5] == 1`.
  - **Unshifted:** `payload[0] == 161`, Battery is at `payload[5]`, Charging flag at `payload[4] == 1`.

### Getting Polling Rate
- **Request:** `[0x00, 0x00, 0x02, 0x82, <1 wireless / 0 wired>, ...]`
- **Response Byte Positions:** 
  - **Shifted:** `payload[5]`
  - **Unshifted:** `payload[4]`

### Setting Polling Rate
- **Request:** `[0x00, 0x00, 0x02, 0x02, <1 wireless / 0 wired>, <freq_byte>, ...]`

The reference driver's `setReportOld` applies the wireless routing byte to
battery, polling queries, and polling writes alike. These routing bytes are
confirmed from source; no old-protocol device was available for hardware tests.

---

## 3. "Compx" Protocol

Experimental compatibility path, excluded from automatic protocol probing.
The bundled reference driver uses 16-byte command payloads over output/input
reports (`writeFile` and its data callback). This application's retained path
uses 17-byte feature reports including the report ID. That transport has not
been validated against hardware, so a passing parser test does not establish
support for a Compx device.

### Getting Battery
- **Request:** `[0x00, 0x04, ...]`
- **Validation:** report ID `0`, exactly 16 payload bytes, and `payload[0] == 0x04`
  to match the requested command. A zero-filled response is invalid.
- **Response Byte Positions:**
  - Battery is at `payload[5]`.
  - Charging flag at `payload[6] == 1`.

## Evidence and remaining limits

The bundled [reference driver](../scratch/index.js) supplies `getBatPer`,
`getOldBattery`, `getProfileID`, `getPollingRate`, `setPollingRate`,
`getPollRate`, `setPollRate`, `setReportOld`, and `retrySetGetWithDelayCompx`.
In particular, the Compx retry helper checks both payload length and the echoed
command. New-protocol report prefixes and battery offsets also appear in
[the original read diagnostic](../scripts/test_read.py).

On 2026-10-04, read-only verification with a wired Fenrir Pro (`0x3608`) returned
active profile `1` and polling byte `0x80` (8000 Hz) for that profile. The old
implementation incorrectly used selector `2` for wired devices, receiving a
zero rate byte. The captured response prefixes were:

```text
Active profile: 00 a1 00 02 01 00 85 01
Polling rate:   00 a1 00 02 02 01 80 01 80
```

No polling settings were changed during this verification. Other models and
firmware versions still need hardware confirmation.

[Protocol regression tests](../tests/test_protocols.py) use synthetic HID
responses to cover both offsets, known rate mappings, malformed replies,
profile selection, failed writes, and transport errors. These tests never open a HID device and
do not establish compatibility across all devices in the model registry.
