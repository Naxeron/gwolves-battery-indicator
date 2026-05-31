# G-Wolves Battery Indicator

A lightweight, universal system tray application for Linux that displays the real-time battery status, charging state, and polling rate of G-Wolves wireless gaming mice. 

![Battery Status](https://img.shields.io/badge/G--Wolves-Battery--Indicator-blue)
![Platform Linux](https://img.shields.io/badge/platform-linux-lightgrey)

## Features
- **Universal Support**: Dynamically probes and supports nearly all modern G-Wolves wireless mice and 1K/4K/8K receivers (including Fenrir, HSK Pro, HTX, HTS, etc.) via reverse-engineered "new", "old", and "compx" USB HID protocols.
- **Live Tray Icon**: Displays the exact battery percentage directly in the system tray.
- **Dynamic Color States**: The icon color updates based on the battery status:
  - ⚡ **Bright Green**: Charging.
  - 🔴 **Red**: Low battery (< 20%).
  - 🟠 **Amber**: Medium battery (< 50%).
  - 🔵 **Light Blue**: Good battery status (>= 50%).
  - ⚪ **Grey**: Disconnected / Error state.
- **Low Battery Notifications**: Sends a desktop notification warning when the battery drops to 15% or below.
- **Polling Rate Control**: Set your mouse's polling rate (from 125Hz up to 8000Hz depending on your receiver capabilities) easily by clicking or scrolling on the tray menu!
- **Asynchronous Polling**: Checks battery state and connection on a background thread to keep the desktop environment responsive.

---

## 📚 Project Wiki

For a deep-dive into how to add new devices, debug udev issues, or understand the G-Wolves USB protocols we reverse-engineered, please visit the **[Project Wiki](https://github.com/Naxeron/gwolves-battery-indicator/wiki)** (or check the `docs/` folder in this repository).

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
By default, Linux blocks non-root applications from reading raw HID devices (`/dev/hidraw*`). To run the indicator as a normal user without `sudo`, you must configure a universal `udev` rule for the G-Wolves Vendor ID:

1. Create a rules file for the G-Wolves receiver:
   ```bash
   sudo nano /etc/udev/rules.d/99-gwolves-universal.rules
   ```
2. Paste the following rule (Vendor ID `33e4`):
   ```udev
   KERNEL=="hidraw*", ATTRS{idVendor}=="33e4", MODE="0666"
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
Launch the application using Python:
```bash
python3 gwolves_indicator.py
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
3. Update the `Exec` line to point to the correct absolute path of the new script:
   ```desktop
   Exec=python3 /home/naxeron/Projects/gwolves-battery-indicator/gwolves_indicator.py
   ```
