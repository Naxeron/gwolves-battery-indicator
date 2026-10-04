# Troubleshooting

## Start with diagnostics

Run these commands from the Python environment used to install the app:

```bash
gwolves-battery --diagnose
gwolves-battery --once
gwolves-battery --debug
```

`--diagnose` lists G-Wolves HID interfaces as JSON without opening them or sending commands. `--once` opens candidate interfaces and reads a status snapshot without changing device settings. Debug mode includes details that help distinguish access errors from unrecognized protocol responses. Close any existing tray instance before using `--once` or debugging live communication.

For a source checkout, substitute `python3 gwolves_indicator.py` for `gwolves-battery`. When reporting a problem, include the device model, wired/wireless connection, firmware version if known, your Linux desktop, and diagnostic output. Review paths and identifiers before posting them publicly.

## Device access fails

A receiver can enumerate successfully while permission checks prevent opening it. Install the checked-in `70-gwolves.rules` from the repository root:

```bash
sudo install -m 0644 70-gwolves.rules /etc/udev/rules.d/70-gwolves.rules
sudo udevadm control --reload-rules
```

Unplug and reconnect the device. The rule grants the active local desktop user access to both hidraw and USB nodes for vendor `33e4`. It depends on a seat/session manager applying `uaccess` ACLs; it does not automatically grant SSH or service accounts access. On such systems, ask the administrator to configure access for the intended account.

Old versions recommended `MODE="0666"` rules. Review and remove any obsolete `99-gwolves-universal.rules` or `99-gwolves.rules` that you installed under `/etc/udev/rules.d`; installing the new rule does not undo permissions granted by an old rule.

Close the G-Wolves web driver and other mouse configuration programs, then try again. An open failure may indicate permissions or another application using the interface; a failed protocol response can instead mean sleeping hardware, an unsupported interface, or an unsupported firmware revision. Running the tray application as root is not required.

## Receiver disconnected or battery unavailable

- Check that `lsusb` shows vendor ID `33e4` and that `--diagnose` lists the expected interface.
- Wake the mouse, confirm its wireless mode, or try a direct USB connection.
- If several receivers are connected, temporarily unplug the others while diagnosing. The app displays one responding device.
- A product name containing “Wireless” can still describe a wired HID interface. Mapped product IDs take precedence over that name.

If enumeration works but the snapshot still reports unsupported or invalid responses, collect the model and product ID for a [device-support report](Adding-Devices.md). A charging battery can legitimately report 100%; the indicator preserves that reading.

## Polling rate is unknown or a change fails

An unknown rate means no recognized value was read. It is not evidence that the rate is 1000 Hz. Unknown product IDs do not expose write controls until their protocol and capabilities are mapped. Available rates are based on the model's capabilities, and a request can still fail because of firmware or connection state. The tray reports a failed change; check debug output for details.

## No tray icon

Your desktop must provide a system tray/status notifier host. On GNOME, this commonly requires a compatible tray extension. Check the desktop's tray configuration before changing Qt settings.

Run from a terminal to see startup errors. If Qt reports a Wayland platform issue and your session supports XWayland, try:

```bash
QT_QPA_PLATFORM=xcb gwolves-battery
```

This can work around a Qt platform problem but does not provide a missing tray host. Install any missing Qt platform libraries using your distribution's package manager. A headless session can use `--diagnose` and `--once` without a tray.

## Launcher or autostart no longer works

The generated entry stores the absolute Python interpreter path, so moving or deleting a virtual environment breaks it. Activate the working environment and run `gwolves-install` again. Use `gwolves-install --no-autostart` to disable login startup. The installer respects absolute `XDG_CONFIG_HOME` and `XDG_DATA_HOME` values, falling back to the standard home directories when unset or invalid.
