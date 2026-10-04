# G-Wolves Battery Indicator

A Linux system tray application for reading the battery percentage, charging state, and polling rate of G-Wolves mice and receivers. It uses PyQt6 and reverse-engineered HID protocols; it is not an official G-Wolves utility.

![G-Wolves Battery Indicator screenshot](screenshot.png)

![Platform Linux](https://img.shields.io/badge/platform-linux-lightgrey)

## What works

- Battery and charging status in a tray icon, refreshed every 5 seconds by default.
- Background device communication, manual refresh, and low-battery notifications.
- Polling-rate controls for mapped devices, with failures reported instead of displayed as successful changes.
- Headless diagnostics and a single battery snapshot for troubleshooting or scripts.

The device table covers several HTX, HTS, HSK, HTR, Fenrir, Lycan, and related revisions. A table entry is a protocol mapping, not a claim that every firmware version has been tested. Unknown product IDs can be probed using the `new` and `old` battery protocols; their polling-rate controls remain disabled until mapped. The experimental `compx` protocol is not probed automatically. See [device support](docs/Adding-Devices.md) and [protocol notes](docs/Protocols.md).

## Install

Requirements: Linux, Python 3.10 or newer, a desktop session with a system tray, and a G-Wolves USB device (vendor ID `33e4`). From this checkout:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
gwolves-battery
```

Keep the virtual environment at the same path after creating desktop entries. Python dependencies are declared in `pyproject.toml`; `pip install .` installs them without changing desktop settings.

### USB permissions

Install the included rule to grant access to the active local desktop session through `uaccess`:

```bash
sudo install -m 0644 70-gwolves.rules /etc/udev/rules.d/70-gwolves.rules
sudo udevadm control --reload-rules
```

Then unplug and reconnect the receiver or mouse. The rule covers both hidraw and USB device nodes, for the two hidapi backends. It does not grant access to every user. Sessions without a seat manager, such as a headless SSH session, may need permissions configured by their administrator.

If you installed an older `99-gwolves-universal.rules` or `99-gwolves.rules` containing `MODE="0666"`, remove that old rule after reviewing it; it otherwise continues granting access to every user. The new installer does not remove existing rules or run privileged commands.

### Launcher and login autostart

With the same virtual environment active:

```bash
gwolves-install
```

This creates an application-menu entry and enables autostart at login. To install the launcher and disable autostart, including a previous installation:

```bash
gwolves-install --no-autostart
```

Entries are written under `$XDG_DATA_HOME/applications` and `$XDG_CONFIG_HOME/autostart`, defaulting to `~/.local/share/applications` and `~/.config/autostart`. Installation errors return a nonzero exit code. Re-run the installer after moving or recreating your environment.

For existing source-based installations, `python3 setup.py` remains a desktop-setup shortcut and `python3 setup.py --no-autostart` disables autostart. Install the dependencies in that interpreter first. The source entry point `python3 gwolves_indicator.py` also remains available.

## Use

```bash
gwolves-battery                  # start the tray application
gwolves-battery --interval 10    # check every 10 seconds (minimum: 1)
gwolves-battery --diagnose       # enumerate devices as JSON without opening them
gwolves-battery --once           # query one status snapshot as JSON
gwolves-battery --debug          # include diagnostic logging
gwolves-battery --help
```

`--once` sends the HID queries needed to read status; `--diagnose` only enumerates devices. Neither changes the polling-rate setting. Tray controls let you refresh, change supported polling rates, and quit. An unreadable polling rate is shown as unknown.

Only one tray instance runs per user session. `--once` exits with status 0 when a mouse responds and 1 when it cannot read a device; unavailable values are JSON `null`. Close the tray before querying a snapshot to avoid overlapping HID requests.

See [troubleshooting](docs/Troubleshooting.md) for device access and tray problems.

## Development

```bash
python -m pip install -e '.[dev]'
python -m pytest
python -m pytest --cov=gwolves --cov-report=term-missing
python -m build
```

Tests use simulated devices and temporary desktop directories. Pytest is restricted to `tests/`: files in `scripts/` are manual hardware experiments and may send configuration commands. Review those scripts before running them on a device. CI tests Python 3.10, 3.12, and 3.14 with Qt's offscreen platform and builds the package.

Documentation is maintained in [docs/](docs/Home.md). Automated tests verify software behavior; battery accuracy, firmware compatibility, and actual polling-rate changes still require validation on the relevant hardware.
