"""Command-line entry points; diagnostics do not require a graphical session."""

import argparse
from importlib import metadata
import json
import logging
import math
import os
from pathlib import Path
import signal
import sys
from threading import TIMEOUT_MAX

from gwolves import __version__


def _interval(value):
    try:
        interval = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("interval must be a number") from exc
    if not math.isfinite(interval) or not 1 <= interval <= TIMEOUT_MAX:
        raise argparse.ArgumentTypeError(f"interval must be between 1 and {TIMEOUT_MAX:g} seconds")
    return interval


def _json(data):
    print(json.dumps(data, indent=2, ensure_ascii=True))


def _diagnose():
    from gwolves.protocols import MODELS, VID

    versions = {}
    for package in ("hidapi", "PyQt6"):
        try:
            versions[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            versions[package] = "not installed as a Python distribution"
    result = {"version": __version__, "python": sys.version.split()[0],
              "dependencies": versions, "devices": []}
    try:
        import hid
        from gwolves.reader import device_is_wireless

        for info in hid.enumerate(VID):
            model, protocol = MODELS.get(info["product_id"], ("Unknown G-Wolves", None))
            result["devices"].append({
                "path": os.fsdecode(info["path"]),
                "vendor_id": f"0x{info['vendor_id']:04x}",
                "product_id": f"0x{info['product_id']:04x}",
                "product": info.get("product_string"),
                "interface": info.get("interface_number"),
                "usage_page": info.get("usage_page"),
                "usage": info.get("usage"),
                "model": model,
                "protocol": protocol,
                "connection": "wireless" if device_is_wireless(info, model) else "wired",
            })
    except (ImportError, OSError, RuntimeError) as exc:
        result["error"] = str(exc)
        _json(result)
        return 1
    _json(result)
    return 0


def _once():
    try:
        from gwolves.reader import BatteryMonitor
        status, _ = BatteryMonitor().poll()
    except (ImportError, OSError, RuntimeError) as exc:
        _json({"connected": False, "error": str(exc)})
        return 1
    _json({
        "connected": status.connected,
        "model": status.model,
        "percentage": status.percentage if status.connected else None,
        "charging": status.charging if status.connected else None,
        "polling_rate": status.polling_rate or None,
        "supported_rates": status.supported_rates,
        "protocol": status.protocol,
        "path": os.fsdecode(status.path) if status.path is not None else None,
        "error": status.error or None,
    })
    return 0 if status.connected else 1


def _run_tray(poll_interval):
    if not any(os.environ.get(name) for name in ("DISPLAY", "WAYLAND_DISPLAY", "QT_QPA_PLATFORM")):
        print("No graphical session found. Use --diagnose or --once in a terminal.", file=sys.stderr)
        return 1
    try:
        from PyQt6.QtCore import QLockFile, QStandardPaths, QTimer
        from PyQt6.QtWidgets import QSystemTrayIcon
        from gwolves.ui import GWolvesBatteryApp
    except ImportError as exc:
        print(f"Missing runtime dependency: {exc}. Install this project with pip first.", file=sys.stderr)
        return 1

    runtime_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.RuntimeLocation)
    lock = QLockFile(str(Path(runtime_dir) / "gwolves-battery-indicator.lock"))
    # Do not age out a lock belonging to a long-running tray process.
    lock.setStaleLockTime(0)
    if not lock.tryLock(0):
        if lock.error() == QLockFile.LockError.LockFailedError:
            print("G-Wolves Battery Indicator is already running.", file=sys.stderr)
            return 0
        print("Cannot create the session lock for G-Wolves Battery Indicator.", file=sys.stderr)
        return 1

    previous_handlers = {}
    app = None
    try:
        app = GWolvesBatteryApp([sys.argv[0]], poll_interval=poll_interval)
        if not QSystemTrayIcon.isSystemTrayAvailable():
            logging.getLogger(__name__).warning(
                "No system tray host is available yet. Waiting for the desktop tray; "
                "use --once for terminal output."
            )
        # Periodic Python callbacks let Python's signal handlers run in Qt's loop.
        timer = QTimer(app)
        timer.timeout.connect(lambda: None)
        timer.start(250)
        for signum in (signal.SIGINT, signal.SIGTERM):
            previous_handlers[signum] = signal.signal(signum, lambda *_: app.quit())
        logging.getLogger(__name__).info("Tray indicator started; refresh interval %.1f seconds", poll_interval)
        return app.exec()
    finally:
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)
        if app is not None:
            app.stop_reader()
        lock.unlock()


def main(argv=None):
    parser = argparse.ArgumentParser(description="G-Wolves mouse battery indicator for Linux")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--diagnose", action="store_true", help="enumerate HID interfaces as JSON without opening devices")
    modes.add_argument("--once", action="store_true", help="read one battery status as JSON without starting the tray")
    parser.add_argument("--interval", type=_interval, default=5.0, metavar="SECONDS", help="battery refresh interval (default: 5, minimum: 1)")
    parser.add_argument("--debug", action="store_true", help="log device diagnostics to stderr")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")
    if args.diagnose:
        return _diagnose()
    if args.once:
        return _once()
    return _run_tray(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
