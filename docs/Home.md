# G-Wolves Battery Indicator

Welcome to the **G-Wolves Battery Indicator** wiki! This project provides a lightweight system tray application for Linux that displays the real-time battery status and charging state of G-Wolves wireless gaming mice.

## Features
- **Live Tray Icon:** Displays exact battery percentage directly in your system tray.
- **Dynamic Color States:** Green (charging), Red (<20%), Amber (<50%), Blue (>=50%), Grey (Disconnected).
- **Asynchronous Polling:** Background threaded polling (every 60 seconds) without freezing your UI.
- **Polling Rate Control:** Easily set your mouse's polling rate (125Hz - 8000Hz depending on model) from the tray context menu.
- **Universal Support Engine:** The program dynamically probes unknown G-Wolves receivers and maps them to the appropriate communication protocol (`new`, `old`, or `compx`).

## Quick Navigation
- **[Protocols](Protocols.md)**: Deep-dive into the reverse-engineered USB HID protocols.
- **[Adding Devices](Adding-Devices.md)**: Guide to understanding how devices are detected and how to map new ones.
- **[Troubleshooting](Troubleshooting.md)**: Solutions for common Linux issues (`udev` rules, wayland compatibility).
