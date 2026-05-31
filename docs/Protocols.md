# USB HID Protocols

G-Wolves uses several different proprietary USB HID feature report protocols for requesting and setting device data. This application currently handles three distinct protocols, internally named: `new`, `old`, and `compx`.

All devices share the same Vendor ID: `0x33e4`.

---

## 1. "New" Protocol

Typically found on newer mice (e.g., Fenrir Pro, HTXU, models with `IsNewProtocol = "1"`). 
This protocol utilizes long 65-byte Feature Reports.

### Getting Battery
- **Payload:** `[0x00, 0x00, 0x00, 0x02, 0x02, 0x00, 0x83, ...]`
- **Response Byte Positions:**
  Depending on whether the driver shifts the response by 1 byte (which happens on some kernels/HID API versions):
  - **Shifted:** `payload[1] == 161`, Battery is at `payload[8]`, Charging flag at `payload[7] == 1`.
  - **Unshifted:** `payload[0] == 161`, Battery is at `payload[7]`, Charging flag at `payload[6] == 1`.

### Getting Polling Rate
- **Payload:** `[0x00, 0x00, 0x00, 0x02, 0x02, 0x01, 0x80, <1 for wireless, 2 for wired>, ...]`
- **Response Byte Positions:** 
  The polling rate byte is mapped using a specific chart (`128` = 8000Hz, `64` = 4000Hz, `1` = 1000Hz, `2` = 500Hz, etc.).
  - **Shifted:** `payload[8]`
  - **Unshifted:** `payload[7]`

### Setting Polling Rate
- **Payload:** `[0x00, 0x00, 0x00, 0x02, 0x02, 0x01, 0x00, <1 wireless / 2 wired>, <freq_byte>, ...]`

---

## 2. "Old" Protocol

Typically found on older mice (e.g., HSK Pro, HTX, models with `IsNewProtocol = "0"`).

### Getting Battery
- **Payload:** `[0x00, 0x00, 0x02, 0x8F, <1 wireless / 0 wired>, ...]`
- **Response Byte Positions:**
  - **Shifted:** `payload[1] == 161`, Battery is at `payload[6]`, Charging flag at `payload[5] == 1`.
  - **Unshifted:** `payload[0] == 161`, Battery is at `payload[5]`, Charging flag at `payload[4] == 1`.

### Getting Polling Rate
- **Payload:** `[0x00, 0x00, 0x02, 0x82, ...]`
- **Response Byte Positions:** 
  - **Shifted:** `payload[5]`
  - **Unshifted:** `payload[4]`

### Setting Polling Rate
- **Payload:** `[0x00, 0x00, 0x02, 0x02, 0x00, <freq_byte>, ...]`

---

## 3. "Compx" Protocol

A rare alternative protocol observed on some legacy/OEM models. Uses 17-byte Feature Reports.

### Getting Battery
- **Payload:** `[0x00, 0x04, ...]`
- **Response Byte Positions:**
  - Battery is at `payload[5]`.
  - Charging flag at `payload[6] == 1`.
