import json
import sys
from unittest.mock import Mock

import pytest

from gwolves import cli
from gwolves.reader import BatteryStatus


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf", "1e300", "text"])
def test_interval_rejects_invalid_values(value):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--interval", value])
    assert exc.value.code == 2


def test_diagnostics_enumerates_without_opening_or_exposing_serials(monkeypatch, capsys):
    backend = Mock()
    backend.enumerate.return_value = [{
        "path": b"/dev/hidraw0", "vendor_id": 0x33E4, "product_id": 0x3608,
        "serial_number": "private serial", "product_string": "Wireless Mouse",
        "interface_number": 2, "usage_page": 0xFFFF, "usage": 1,
    }]
    monkeypatch.setitem(sys.modules, "hid", backend)
    assert cli.main(["--diagnose"]) == 0
    output = capsys.readouterr().out
    data = json.loads(output)
    assert data["devices"][0]["connection"] == "wired"
    assert "private serial" not in output
    backend.device.assert_not_called()


@pytest.mark.parametrize("connected,code", [(True, 0), (False, 1)])
def test_once_returns_json_and_connection_exit_status(monkeypatch, capsys, connected, code):
    monitor = Mock()
    monitor.poll.return_value = (BatteryStatus(percentage=0, connected=connected), None)
    monkeypatch.setattr("gwolves.reader.BatteryMonitor", Mock(return_value=monitor))
    assert cli.main(["--once"]) == code
    data = json.loads(capsys.readouterr().out)
    assert data["connected"] is connected
    assert data["percentage"] == (0 if connected else None)
    assert data["polling_rate"] is None
    monitor.poll.assert_called_once_with()


def test_diagnostics_reports_transport_failure(monkeypatch, capsys):
    backend = Mock()
    backend.enumerate.side_effect = OSError("USB unavailable")
    monkeypatch.setitem(sys.modules, "hid", backend)
    assert cli.main(["--diagnose"]) == 1
    assert "USB unavailable" in json.loads(capsys.readouterr().out)["error"]


def test_tray_receives_interval(monkeypatch):
    run = Mock(return_value=0)
    monkeypatch.setattr(cli, "_run_tray", run)
    assert cli.main(["--interval", "12"]) == 0
    assert run.call_args.args[0] == 12


def test_no_graphical_session_has_actionable_error(monkeypatch, capsys):
    for name in ("DISPLAY", "WAYLAND_DISPLAY", "QT_QPA_PLATFORM"):
        monkeypatch.delenv(name, raising=False)
    assert cli._run_tray(5) == 1
    assert "--once" in capsys.readouterr().err


def test_missing_runtime_dependencies_have_actionable_error(monkeypatch, capsys):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setitem(sys.modules, "PyQt6.QtWidgets", None)
    assert cli._run_tray(5) == 1
    assert "Missing runtime dependency" in capsys.readouterr().err


def test_once_handles_missing_hid_dependency(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "gwolves.reader", None)
    assert cli.main(["--once"]) == 1
    assert json.loads(capsys.readouterr().out)["connected"] is False


def test_help_works_without_gui_or_hid_imports():
    import subprocess
    result = subprocess.run(
        [sys.executable, "-c", "from gwolves.cli import main; import sys; "
         "sys.modules['hid'] = None; sys.modules['PyQt6'] = None; main(['--help'])"],
        text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0
    assert "--diagnose" in result.stdout


def test_tray_lifecycle_and_single_instance(tmp_path):
    """Exercise real Qt startup, lock contention and SIGTERM without real HID."""
    import os
    from pathlib import Path
    import subprocess
    import time

    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    log = tmp_path / "tray.log"
    # Replace only HID in the child interpreter, leaving real Qt/CLI behavior.
    fake_modules = tmp_path / "modules"
    fake_modules.mkdir()
    (fake_modules / "hid.py").write_text("def enumerate(*args): return []\n")
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", XDG_RUNTIME_DIR=str(runtime),
               PYTHONPATH=os.pathsep.join([str(fake_modules), str(Path(__file__).parents[1])]))
    command = [sys.executable, "-m", "gwolves", "--debug", "--interval", "3600"]
    with log.open("w") as output:
        process = subprocess.Popen(command, cwd=tmp_path, env=env, stdout=output, stderr=output)
        try:
            deadline = time.monotonic() + 10
            while "Tray indicator started" not in log.read_text():
                assert process.poll() is None, log.read_text()
                assert time.monotonic() < deadline, log.read_text()
                time.sleep(0.02)
            second = subprocess.run(command, cwd=tmp_path, env=env, capture_output=True, text=True, timeout=10)
            assert second.returncode == 0
            assert "already running" in second.stderr
            process.terminate()
            assert process.wait(timeout=5) == 0
            assert not (runtime / "gwolves-battery-indicator.lock").exists()
            assert "QThread: Destroyed" not in log.read_text()
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
