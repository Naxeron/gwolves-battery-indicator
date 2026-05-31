# Troubleshooting

### Indicator shows `?` and Tooltip says "Permission denied / Device busy"
This means Python cannot access the receiver's raw HID interface `/dev/hidraw*`. By default, Linux blocks non-root applications from reading these files. 

You must configure a `udev` rule:

1. Create a rules file for the G-Wolves receiver:
   ```bash
   sudo nano /etc/udev/rules.d/99-gwolves.rules
   ```
2. Paste the following rule (Vendor ID `33e4`):
   ```udev
   KERNEL=="hidraw*", ATTRS{idVendor}=="33e4", MODE="0666"
   ```
3. Reload the `udev` daemon:
   ```bash
   sudo udevadm control --reload-rules
   sudo udevadm trigger
   ```
4. **Unplug and replug** your G-Wolves USB receiver.

### Indicator shows `?` and Tooltip says "Receiver disconnected"
Make sure the USB receiver is plugged directly into a working USB port. The background thread checks for Vendor ID `0x33e4`. If `lsusb` does not show this device, it's not connected.

### Application fails to start or System Tray doesn't show (Wayland)
If you are running a Wayland session (GNOME, KDE Plasma) and the system tray does not appear, try overriding the Qt platform plugin before launching:

```bash
QT_QPA_PLATFORM=xcb python3 gwolves_indicator.py
```

### Using the Official Web App (mouse.xyz)
When using the official G-Wolves web driver at `mouse.xyz`, keep the following officially recommended tips in mind:
- **Browser Compatibility**: The web driver requires the WebHID API, so you **must** use a Chromium-based browser like Google Chrome or Microsoft Edge.
- **Desktop Software**: To use the web driver, you must turn off any desktop driver software first.
- **Dongle Conflicts**: Only one 1K dongle can be connected at a time while configuring.
- **Battery Display Issues**: If the battery does not display, first click "Disconnect," then click "Connect."
- **Offline Device**: If the device shows as offline, wake up the mouse or make sure the switch on the bottom is set to 2.4G.
- **Firmware Updates**: During DFU updates, ensure only one receiver is connected.
