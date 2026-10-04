"""Desktop installation never needs real home directories or USB hardware."""

import runpy
import sys
from pathlib import Path
from types import ModuleType

import pytest

from gwolves import install


@pytest.fixture
def desktop_dirs(tmp_path, monkeypatch):
    config = tmp_path / "config"
    data = tmp_path / "data"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    monkeypatch.setenv("XDG_DATA_HOME", str(data))
    return config, data


def test_installs_launchable_entries_only_in_xdg_dirs(desktop_dirs, tmp_path, monkeypatch):
    config, data = desktop_dirs
    monkeypatch.chdir(tmp_path)
    paths = install.install_desktop_entries(["/opt/Python Env/bin/python", "-m", "gwolves.cli"])

    assert set(paths) == {
        data / "applications/gwolves-battery.desktop",
        config / "autostart/gwolves-battery.desktop",
    }
    for path in paths:
        content = path.read_text()
        assert 'Exec="/opt/Python Env/bin/python" "-m" "gwolves.cli"\n' in content
        assert "Hidden=true" not in content
        assert path.stat().st_mode & 0o777 == 0o644
    assert not (tmp_path / "gwolves-battery.desktop").exists()


def test_no_autostart_disables_an_existing_entry(desktop_dirs):
    config, data = desktop_dirs
    install.install_desktop_entries(["/usr/bin/python3", "-m", "gwolves.cli"])
    install.install_desktop_entries(["/usr/bin/python3", "-m", "gwolves.cli"], autostart=False)

    assert "Hidden=true\n" in (config / "autostart/gwolves-battery.desktop").read_text()
    assert "Hidden=true" not in (data / "applications/gwolves-battery.desktop").read_text()


@pytest.mark.parametrize("value", ["", "relative/path"])
def test_invalid_xdg_paths_fall_back_to_home(tmp_path, monkeypatch, value):
    monkeypatch.setenv("XDG_CONFIG_HOME", value)
    monkeypatch.setenv("XDG_DATA_HOME", value)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    paths = install.install_desktop_entries(["/usr/bin/python3", "-m", "gwolves.cli"])

    assert tmp_path / ".config/autostart/gwolves-battery.desktop" in paths
    assert tmp_path / ".local/share/applications/gwolves-battery.desktop" in paths


def test_exec_escapes_desktop_field_codes_and_reserved_characters():
    content = install.desktop_content(["/usr/bin/python3", '/tmp/space %f/$cash`tick"quote\\file.py'])
    assert 'Exec="/usr/bin/python3" "/tmp/space %%f/\\\\$cash\\\\`tick\\\\"quote\\\\\\\\file.py"\n' in content


@pytest.mark.parametrize("argument", ["bad\nName=Injected", "bad\rline", "bad\x00path"])
def test_exec_rejects_invalid_paths(argument):
    with pytest.raises(ValueError):
        install.desktop_content(["/usr/bin/python3", argument])


def test_exec_rejects_equals_in_executable():
    with pytest.raises(ValueError, match="executable"):
        install.desktop_content(["/tmp/python=env/bin/python"])


def test_atomic_entry_replacement_does_not_follow_existing_symlink(desktop_dirs, tmp_path):
    _, data = desktop_dirs
    original = tmp_path / "keep.txt"
    original.write_text("keep me")
    applications = data / "applications"
    applications.mkdir(parents=True)
    entry = applications / "gwolves-battery.desktop"
    entry.symlink_to(original)

    install.install_desktop_entries(["/usr/bin/python3", "-m", "gwolves.cli"])

    assert original.read_text() == "keep me"
    assert not entry.is_symlink()


def test_missing_dependencies_do_not_create_broken_launchers(desktop_dirs, monkeypatch, capsys):
    monkeypatch.setattr(install, "check_dependencies", lambda: ["hidapi: not installed"])

    assert install.main([]) == 1
    assert "hidapi" in capsys.readouterr().err
    assert all(not directory.exists() for directory in desktop_dirs)


def test_write_errors_return_failure(desktop_dirs, monkeypatch, capsys):
    monkeypatch.setattr(install, "check_dependencies", lambda: [])

    def fail(*args, **kwargs):
        raise PermissionError("read-only directory")

    monkeypatch.setattr(install, "install_desktop_entries", fail)

    assert install.main([]) == 1
    output = capsys.readouterr()
    assert "read-only directory" in output.err
    assert "complete" not in output.out.lower()


def test_successful_install_honors_no_autostart(desktop_dirs, monkeypatch, capsys):
    config, data = desktop_dirs
    monkeypatch.setattr(install, "check_dependencies", lambda: [])

    assert install.main(["--no-autostart"]) == 0
    assert "Hidden=true\n" in (config / "autostart/gwolves-battery.desktop").read_text()
    assert "Login autostart disabled" in capsys.readouterr().out
    assert (data / "applications/gwolves-battery.desktop").is_file()


def test_dependency_checks_report_broken_shared_libraries(monkeypatch):
    def import_module(module):
        if module == "hid":
            raise OSError("libhidapi.so missing")

    monkeypatch.setattr(install.importlib, "import_module", import_module)

    assert install.check_dependencies() == ["hidapi: libhidapi.so missing"]


def test_source_launcher_preserves_virtual_environment_interpreter(tmp_path, monkeypatch):
    interpreter = tmp_path / "env/bin/python"
    interpreter.parent.mkdir(parents=True)
    interpreter.symlink_to(sys.executable)
    monkeypatch.setattr(sys, "executable", str(interpreter))

    command = install._launcher_command()

    assert command[0] == str(interpreter)
    assert command[1] == str(Path(__file__).parents[1] / "gwolves_indicator.py")


def test_installed_launcher_works_without_a_source_checkout(tmp_path, monkeypatch):
    monkeypatch.setattr(install, "__file__", str(tmp_path / "site-packages/gwolves/install.py"))

    command = install._launcher_command()

    assert command == [sys.executable, "-m", "gwolves.cli"]


def test_packaging_invocation_does_not_run_desktop_installer(monkeypatch):
    calls = []
    setuptools = ModuleType("setuptools")
    setuptools.setup = lambda: calls.append("packaging")
    monkeypatch.setitem(sys.modules, "setuptools", setuptools)
    monkeypatch.setattr(sys, "argv", ["setup.py", "--name"])
    monkeypatch.setattr(install, "main", lambda *args: pytest.fail("Installer ran during build"))

    runpy.run_path(str(Path(__file__).parents[1] / "setup.py"), run_name="__main__")

    assert calls == ["packaging"]


def test_legacy_setup_keeps_installer_exit_status(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["setup.py"])
    monkeypatch.setattr(install, "main", lambda args: 1)

    with pytest.raises(SystemExit) as result:
        runpy.run_path(str(Path(__file__).parents[1] / "setup.py"), run_name="__main__")

    assert result.value.code == 1
