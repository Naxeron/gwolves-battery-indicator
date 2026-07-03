# G-Wolves Battery Indicator

![KovaaKs Scenario Tracker Screenshot](screenshot.png)

A lightweight, universal system tray application for Linux that displays the real-time battery status, charging state, and polling rate of G-Wolves wireless gaming mice. 

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
- **Polling Rate Control**: Set your mouse's polling rate (from 125Hz up to 8000Hz depending on your receiver capabilities) easily by clicking on the tray menu!
- **Asynchronous Polling**: Checks battery state and connection on a background thread to keep the desktop environment responsive.

---

## 📚 Project Wiki

For a deep-dive into how to add new devices, debug udev issues, or understand the G-Wolves USB protocols we reverse-engineered, please visit the **[Project Wiki](https://github.com/Naxeron/gwolves-battery-indicator/wiki)** (or check the `docs/` folder in this repository).

---

## Installation & Setup

Run the included setup script to automatically configure desktop shortcuts, generate autostart entries, and check for missing dependencies:

```bash
python3 setup.py
```

The script will guide you through setting up the necessary `udev` rules so that the indicator can read your mouse battery without requiring root privileges.

### Missing Dependencies?
If the setup script detects missing dependencies, you can install them via pip or your system package manager:
```bash
pip install PyQt6 hidapi
```

---

## Usage

After running the setup script, you can launch the application directly from your system app launcher (search for **G-Wolves Battery Indicator**), or start it from the terminal:

```bash
python3 gwolves_indicator.py
```

The application will now automatically run silently in your system tray every time you log in!
