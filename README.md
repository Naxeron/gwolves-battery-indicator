# G-Wolves Battery Indicator

A lightweight system tray application for Linux that displays the real-time battery status and charging state of G-Wolves wireless gaming mice (configured for the G-Wolves Fenrir Pro 8K USB Receiver).

![Battery Status](https://img.shields.io/badge/G--Wolves-Battery--Indicator-blue)
![Platform Linux](https://img.shields.io/badge/platform-linux-lightgrey)

## Features
- **Live Tray Icon**: Displays the exact battery percentage directly in the system tray.
- **Dynamic Color States**: The icon color updates based on the battery status:
  - ⚡ **Bright Green**: Charging (cured/capped at 99% UI state to match G-Wolves client behaviors).
  - 🔴 **Red**: Low battery (< 20%).
  - 🟠 **Amber**: Medium battery (< 50%).
  - 🔵 **Light Blue**: Good battery status (>= 50%).
  - ⚪ **Grey**: Disconnected / Error state.
- **Low Battery Notifications**: Sends a desktop notification warning when the battery drops to 15% or below.
- **Asynchronous Polling**: Periodically checks battery state on a background thread every 60 seconds (or on manual refresh) to keep the desktop environment responsive.
- **Context Menu**: Simple right-click menu with:
  - Current device connection status.
  - Precise battery level and state (Charging vs. Discharging).
  - Quick refresh option.
  - Exit.

---

## Compatibility Warning

### Is this universal?
**No. This utility is not universal.** 

It is designed specifically for G-Wolves wireless mice (using the **G-Wolves Fenrir Pro 8K USB Receiver**, Vendor ID: `0x33e4`, Product ID: `0x3617`). 

Other mice manufacturers (Logitech, Razer, Glorious, SteelSeries, etc.) use different Vendor/Product IDs and separate proprietary USB HID feature report protocols (e.g. Logitech uses HID++) to request battery status. This application will not recognise or poll other brands.

---

## Installation & Setup

### 1. Install System Dependencies
This application requires `hidapi` to communicate with the USB device, and `PyQt6` for the system tray GUI.

#### Install `hidapi` on your Linux distribution:
- **Ubuntu/Debian**:
  ```bash
  sudo apt update
  sudo apt install libhidapi-hidraw0
  ```
- **Fedora/RHEL**:
  ```bash
  sudo dnf install hidapi
  ```
- **Arch Linux**:
  ```bash
  sudo pacman -S hidapi
  ```

### 2. Install Python Packages
Install the required Python wrappers:
```bash
pip install PyQt6 python-hidapi
```

### 3. Setup USB Device Permissions (`udev` rule)
By default, Linux blocks non-root applications from reading raw HID devices (`/dev/hidraw*`). To run the indicator as a normal user without `sudo`, you must configure a `udev` rule:

1. Create a rules file for the G-Wolves receiver:
   ```bash
   sudo nano /etc/udev/rules.d/99-gwolves.rules
   ```
2. Paste the following rule:
   ```udev
   KERNEL=="hidraw*", ATTRS{idVendor}=="33e4", ATTRS{idProduct}=="3617", MODE="0666"
   ```
3. Save and close the file (`Ctrl+O`, `Enter`, then `Ctrl+X` in nano).
4. Reload the `udev` daemon to apply the change:
   ```bash
   sudo udevadm control --reload-rules
   sudo udevadm trigger
   ```
5. **Unplug and replug** your G-Wolves USB receiver.

---

## Usage

### Run from Terminal
Run the application using Python:
```bash
python3 app.py
```

### Autostart on System Login
To make the application start automatically when you log in:

1. Copy the desktop entry file to your user's autostart directory:
   ```bash
   mkdir -p ~/.config/autostart
   cp gwolves-battery.desktop ~/.config/autostart/
   ```
2. Open the desktop file in a text editor:
   ```bash
   nano ~/.config/autostart/gwolves-battery.desktop
   ```
3. Update the `Exec` line to point to the correct absolute path of your script:
   ```desktop
   Exec=python3 /home/naxeron/Projects/gwolves-battery-indicator/app.py
   ```

---

## Troubleshooting

- **Indicator shows `?` and Tooltip says "Permission denied / Device busy"**:
  This means Python cannot access the receiver's `/dev/hidraw*` node. Double check that you've configured the `/etc/udev/rules.d/99-gwolves.rules` file correctly and unplugged/replugged your USB receiver.
- **Indicator shows `?` and Tooltip says "Receiver disconnected"**:
  Make sure the USB receiver is plugged directly into a working USB port.
- **Wayland Environment Issues**:
  If the application fails to start or the system tray doesn't show up on wayland desktops, try launching it using:
  ```bash
  QT_QPA_PLATFORM=xcb python3 app.py
  ```
