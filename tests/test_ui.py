"""Tray behavior tested without a desktop session or mouse hardware."""

import os
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QPainter

from gwolves import ui
from gwolves.reader import BatteryStatus


class FakeReader(QObject):
    status_updated = pyqtSignal(object)
    polling_rate_result = pyqtSignal(int, bool, str)

    def __init__(self, parent=None, poll_interval=5.0):
        super().__init__(parent)
        self.poll_interval = poll_interval
        self.start = Mock()
        self.stop = Mock()
        self.wait = Mock(return_value=True)
        self.trigger_check = Mock()
        self.request_polling_rate = Mock(return_value=True)


class FakeTray:
    MessageIcon = ui.QSystemTrayIcon.MessageIcon

    def __init__(self, parent=None):
        self.setIcon = Mock()
        self.setVisible = Mock()
        self.setContextMenu = Mock()
        self.setToolTip = Mock()
        self.showMessage = Mock()
        self.hide = Mock()


@pytest.fixture(scope="module")
def tray_app():
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(ui, "BatteryReaderThread", FakeReader)
        patch.setattr(ui, "QSystemTrayIcon", FakeTray)
        app = ui.GWolvesBatteryApp([], poll_interval=2.5)
        yield app
        app.stop_reader()


@pytest.fixture
def app(tray_app):
    tray_app.pending_polling_rate = None
    tray_app.low_battery_notified = False
    tray_app.handle_status_update(0, False, False, "Disconnected", "Mouse", 0, [])
    tray_app.tray.showMessage.reset_mock()
    tray_app.reader_thread.request_polling_rate.reset_mock()
    tray_app.reader_thread.request_polling_rate.return_value = True
    return tray_app


def connected(app, percentage=75, charging=False, rate=1000, rates=None):
    app.reader_thread.status_updated.emit(BatteryStatus(
        percentage=percentage, charging=charging, connected=True, error="",
        model="HTX", polling_rate=rate,
        supported_rates=(125, 250, 500, 1000) if rates is None else tuple(rates),
        device_key=(b"mouse", 0x5708, "serial", 1),
    ))


def test_worker_receives_configured_poll_interval(tray_app):
    assert tray_app.reader_thread.poll_interval == 2.5
    tray_app.reader_thread.start.assert_called_once()


def test_polling_request_uses_displayed_device_identity(app):
    identity = (b"shown-mouse", 0x3608, "shown-serial", 1)
    app.reader_thread.status_updated.emit(BatteryStatus(
        percentage=75, connected=True, model="Displayed mouse", polling_rate=1000,
        supported_rates=(500, 1000), device_key=identity,
    ))
    app.set_mouse_polling_rate(500)
    app.reader_thread.request_polling_rate.assert_called_once_with(500, identity)


def test_disconnected_menu_has_no_polling_controls(app):
    connected(app)
    app.handle_status_update(0, False, False, "Disconnected", "HTX", 0, [])
    assert app.current_polling_rate == 0
    assert not app.polling_actions
    assert not app.polling_menu.isEnabled()


def test_unknown_polling_rate_has_no_false_selection(app):
    connected(app, rate=0)
    assert all(not action.isChecked() for action in app.polling_actions.values())
    assert "Rate: Unknown" in app.tray.setToolTip.call_args.args[0]


def test_battery_only_device_has_no_polling_controls(app):
    connected(app, rate=0, rates=[])
    assert not app.polling_actions
    assert not app.polling_menu.isEnabled()


def test_zero_percent_is_drawn_as_zero(app, monkeypatch):
    painter = Mock()
    factory = Mock(return_value=painter)
    factory.RenderHint = QPainter.RenderHint
    monkeypatch.setattr(ui, "QPainter", factory)
    app.create_percentage_icon(0, False, True)
    assert painter.drawText.call_args.args[-1] == "0"


def test_full_charge_number_fits_tray_icon(app, monkeypatch):
    from PyQt6.QtGui import QFontMetrics

    painter = Mock()
    factory = Mock(return_value=painter)
    factory.RenderHint = QPainter.RenderHint
    monkeypatch.setattr(ui, "QPainter", factory)
    app.create_percentage_icon(100, True, True)
    font = painter.setFont.call_args.args[0]
    assert QFontMetrics(font).horizontalAdvance("100") <= 30


def test_zero_percent_warns_once_and_rearms_after_recovery(app):
    connected(app, percentage=0)
    connected(app, percentage=0)
    app.tray.showMessage.assert_called_once()
    assert app.tray.showMessage.call_args.args[:2] == (
        "Low Battery", "HTX battery is low: 0%"
    )
    connected(app, percentage=50)
    connected(app, percentage=10)
    assert app.tray.showMessage.call_count == 2


def test_fully_charged_percentage_is_preserved(app):
    connected(app, percentage=100, charging=True)
    assert app.status_action.text() == "Battery: 100% (Charging)"
    app.tray.showMessage.assert_not_called()


def test_rate_change_stays_pending_until_confirmed(app):
    connected(app)
    app.polling_actions[500].trigger()
    app.reader_thread.request_polling_rate.assert_called_once_with(
        500, (b"mouse", 0x5708, "serial", 1)
    )
    assert app.pending_polling_rate == 500
    assert app.current_polling_rate == 1000
    assert app.polling_actions[1000].isChecked()
    assert not app.polling_menu.isEnabled()
    app.tray.showMessage.assert_not_called()

    connected(app, rate=500)
    assert not app.polling_menu.isEnabled()
    app.reader_thread.polling_rate_result.emit(500, True, "")
    assert app.pending_polling_rate is None
    assert app.polling_menu.isEnabled()
    assert app.polling_actions[500].isChecked()
    assert app.tray.showMessage.call_args.args[:2] == (
        "Polling Rate Changed", "Mouse polling rate set to 500 Hz"
    )


def test_rate_failure_restores_observed_rate_and_reports_reason(app):
    connected(app)
    app.set_mouse_polling_rate(500)
    app.reader_thread.polling_rate_result.emit(500, False, "Readback did not match")
    assert app.pending_polling_rate is None
    assert app.polling_menu.isEnabled()
    assert app.polling_actions[1000].isChecked()
    assert app.tray.showMessage.call_args.args[:2] == (
        "Polling Rate Not Changed", "Readback did not match"
    )


def test_disconnect_during_pending_change_keeps_controls_disabled(app):
    connected(app)
    app.set_mouse_polling_rate(500)
    app.reader_thread.status_updated.emit(BatteryStatus(error="Disconnected", model="HTX"))
    app.reader_thread.polling_rate_result.emit(500, False, "Device disconnected")
    assert app.pending_polling_rate is None
    assert not app.polling_menu.isEnabled()
    assert not app.polling_actions


@pytest.mark.parametrize("rate", [1000, 8000])
def test_unchanged_or_unsupported_rate_is_not_requested(app, rate):
    connected(app)
    app.set_mouse_polling_rate(rate)
    app.reader_thread.request_polling_rate.assert_not_called()


def test_pending_request_cannot_be_overwritten(app):
    connected(app)
    app.set_mouse_polling_rate(500)
    app.set_mouse_polling_rate(250)
    app.reader_thread.request_polling_rate.assert_called_once_with(
        500, (b"mouse", 0x5708, "serial", 1)
    )


def test_rejected_request_does_not_leave_ui_pending(app):
    connected(app)
    app.reader_thread.request_polling_rate.return_value = False
    app.set_mouse_polling_rate(500)
    assert app.pending_polling_rate is None
    assert app.polling_menu.isEnabled()
    assert app.current_polling_rate == 1000
    assert app.tray.showMessage.call_args.args[0] == "Polling Rate Not Changed"


def test_refresh_requests_an_immediate_check(app):
    app.reader_thread.trigger_check.reset_mock()
    app.refresh_action.trigger()
    app.reader_thread.trigger_check.assert_called_once()


def test_quit_signal_stops_and_joins_worker_once(app):
    app.reader_thread.stop.reset_mock()
    app.reader_thread.wait.reset_mock()
    app.aboutToQuit.emit()
    app.stop_reader()
    app.reader_thread.stop.assert_called_once()
    app.reader_thread.wait.assert_called_once()
