"""Install per-user desktop entries without invoking privileged commands."""

import argparse
import importlib
import os
from pathlib import Path
import sys
import tempfile


DESKTOP_NAME = "gwolves-battery.desktop"


def check_dependencies():
    """Return actionable import failures, including missing shared libraries."""
    errors = []
    for module, package in (("hid", "hidapi"), ("PyQt6.QtWidgets", "PyQt6")):
        try:
            importlib.import_module(module)
        except (ImportError, OSError) as exc:
            errors.append(f"{package}: {exc}")
    return errors


def _quote_exec_argument(value):
    """Apply Exec quoting, then the Desktop Entry string escaping layer.

    https://specifications.freedesktop.org/desktop-entry/latest/exec-variables.html
    """
    value = os.fspath(value)
    if any(char in value for char in "\n\r\x00"):
        raise ValueError("Desktop command paths cannot contain newlines or NUL characters")
    value = value.replace("%", "%%")
    value = "".join("\\" + char if char in '\\"`$' else char for char in value)
    value = value.replace("\\", "\\\\").replace("\t", "\\t")
    return f'"{value}"'


def desktop_content(command, *, hidden=False):
    """Return a desktop file with every command argument safely quoted."""
    if not command or not os.fspath(command[0]) or "=" in os.fspath(command[0]):
        raise ValueError("A desktop executable must be nonempty and cannot contain '='")
    executable = " ".join(_quote_exec_argument(arg) for arg in command)
    return (
        "[Desktop Entry]\n"
        "Name=G-Wolves Battery Indicator\n"
        "Comment=System tray battery indicator for G-Wolves mice\n"
        f"Exec={executable}\n"
        "Icon=battery\n"
        "Terminal=false\n"
        "Type=Application\n"
        "Categories=Utility;\n"
        "StartupNotify=false\n"
        + ("Hidden=true\n" if hidden else "")
    )


def _xdg_directory(variable, fallback):
    value = os.environ.get(variable, "")
    if value and Path(value).is_absolute():
        return Path(value)
    return Path.home() / fallback


def _launcher_command():
    # Preserve the venv interpreter path: resolve() would follow its symlink
    # back to the system interpreter and lose the environment's dependencies.
    interpreter = str(Path(sys.executable).absolute())
    source_script = Path(__file__).resolve().parent.parent / "gwolves_indicator.py"
    if source_script.is_file():
        return [interpreter, str(source_script)]
    return [interpreter, "-m", "gwolves.cli"]


def _write_entry(path, content):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=".gwolves-", delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(content)
        temporary.chmod(0o644)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def install_desktop_entries(command=None, *, autostart=True):
    """Create the application entry and explicitly enable or disable autostart.

    Hidden=true also overrides any system-wide entry with the same filename.
    No launchers are generated in the source checkout.
    """
    command = _launcher_command() if command is None else command
    entries = (
        (_xdg_directory("XDG_DATA_HOME", ".local/share") / "applications" / DESKTOP_NAME, False),
        (_xdg_directory("XDG_CONFIG_HOME", ".config") / "autostart" / DESKTOP_NAME, not autostart),
    )
    contents = [desktop_content(command, hidden=hidden) for _, hidden in entries]
    for (path, _), content in zip(entries, contents):
        _write_entry(path, content)
    return [path for path, _ in entries]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-autostart", action="store_true", help="install a launcher but disable login autostart"
    )
    args = parser.parse_args(argv)
    failures = check_dependencies()
    if failures:
        print("Cannot install desktop entries; dependencies could not be loaded:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        print("Install with this Python environment: python -m pip install .", file=sys.stderr)
        return 1

    try:
        paths = install_desktop_entries(autostart=not args.no_autostart)
    except (OSError, ValueError) as exc:
        print(f"Could not install desktop entries: {exc}", file=sys.stderr)
        return 1
    for path in paths:
        print(f"Installed {path}")
    print("Login autostart " + ("disabled." if args.no_autostart else "enabled."))
    if not Path("/etc/udev/rules.d/70-gwolves.rules").is_file():
        print("USB permissions may need configuration; see the README's 70-gwolves.rules instructions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
