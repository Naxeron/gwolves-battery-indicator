from unittest.mock import Mock

import pytest

from gwolves import reader


def interface(path=b"mouse", pid=0x3608, **extra):
    return dict(path=path, vendor_id=reader.VID, product_id=pid,
                product_string="G-Wolves Wireless Mouse", **extra)


def request(path, rate):
    return reader.RateRequest(reader.device_key(interface(path)), rate)


@pytest.fixture
def backend(monkeypatch):
    hid = Mock()
    hid.enumerate.return_value = [interface()]
    monkeypatch.setattr(reader, "query_battery", Mock(return_value=(True, 100, True, "")))
    monkeypatch.setattr(reader, "query_polling_rate", Mock(return_value=None))
    monkeypatch.setattr(reader, "set_polling_rate", Mock(return_value=True))
    return hid


def test_known_pid_overrides_wireless_product_name(backend):
    status, result = reader.BatteryMonitor(backend).poll()
    assert status.connected and status.percentage == 100 and status.charging
    assert status.polling_rate == 0
    assert result is None
    reader.query_battery.assert_called_once_with(backend.device.return_value, "new", False)
    backend.device.return_value.close.assert_called_once()


def test_duplicate_collections_are_opened_once_and_vendor_interface_first(backend):
    backend.enumerate.return_value = [
        interface(b"keyboard", usage_page=1),
        interface(b"vendor", usage_page=1),
        interface(b"vendor", usage_page=0xFF00),
    ]
    reader.query_battery.return_value = (False, 0, False, "Protocol mismatch")
    status, _ = reader.BatteryMonitor(backend).poll()
    assert not status.connected
    assert [call.args[0] for call in backend.device.return_value.open_path.call_args_list] == [b"vendor", b"keyboard"]
    assert "Protocol mismatch" in status.error
    assert "Permission denied" not in status.error


def test_rate_is_written_only_after_battery_validates_target_interface(backend):
    backend.enumerate.return_value = [interface(b"bad"), interface(b"good")]
    reader.query_battery.side_effect = [(False, 0, False, "No response"), (True, 42, False, "")]
    status, result = reader.BatteryMonitor(backend).poll(request(b"bad", 500))
    assert status.connected and status.path == b"good"
    assert result and not result.success
    reader.set_polling_rate.assert_not_called()


@pytest.mark.parametrize("write_ok,readback,success", [(True, 500, True), (True, 1000, False), (True, None, False), (False, 500, False)])
def test_rate_change_requires_write_and_matching_readback(backend, write_ok, readback, success):
    reader.set_polling_rate.return_value = write_ok
    reader.query_polling_rate.return_value = readback
    status, result = reader.BatteryMonitor(backend).poll(request(b"mouse", 500))
    assert result.success is success
    assert result.rate == 500
    assert status.polling_rate == (readback or 0)


def test_disconnected_request_cannot_change_replacement_mouse(backend):
    backend.enumerate.return_value = [interface(b"replacement")]
    status, result = reader.BatteryMonitor(backend).poll(request(b"original", 500))
    assert status.connected
    assert result and not result.success
    reader.set_polling_rate.assert_not_called()


def test_reused_path_with_different_serial_cannot_receive_queued_write(backend):
    backend.enumerate.return_value = [interface(serial_number="replacement")]
    _, result = reader.BatteryMonitor(backend).poll(request(b"mouse", 500))
    assert not result.success
    reader.set_polling_rate.assert_not_called()


def test_unknown_device_probes_without_enabling_rate_writes(backend):
    backend.enumerate.return_value = [interface(pid=0xFFFF)]
    reader.query_battery.side_effect = [(False, 0, False, "Mismatch"), (True, 0, False, "")]
    status, _ = reader.BatteryMonitor(backend).poll()
    assert status.connected and status.percentage == 0
    assert status.protocol == "old" and not status.supported_rates
    assert [c.args[1] for c in reader.query_battery.call_args_list] == ["new", "old"]


def test_protocol_cache_is_per_interface_and_retries_failed_cache(backend):
    backend.enumerate.return_value = [interface(pid=0xFFFF)]
    monitor = reader.BatteryMonitor(backend)
    reader.query_battery.return_value = (True, 20, False, "")
    monitor.poll()
    reader.query_battery.side_effect = [(False, 0, False, "Mismatch"), (True, 30, False, "")]
    status, _ = monitor.poll()
    assert status.connected and status.protocol == "old"


def test_permission_error_preserves_reason_and_closes_handle(backend):
    backend.device.return_value.open_path.side_effect = OSError("Permission denied")
    status, _ = reader.BatteryMonitor(backend).poll()
    assert not status.connected and "Permission denied" in status.error
    backend.device.return_value.close.assert_called_once()


def test_no_receiver_and_enumeration_error(backend):
    backend.enumerate.return_value = []
    monitor = reader.BatteryMonitor(backend)
    assert "disconnected" in monitor.poll()[0].error
    backend.enumerate.side_effect = OSError("USB failed")
    assert "USB failed" in monitor.poll()[0].error


def test_unsupported_rate_is_never_written(backend):
    _, result = reader.BatteryMonitor(backend).poll(request(b"mouse", 123))
    assert not result.success
    reader.set_polling_rate.assert_not_called()


def test_preferred_interface_is_kept_across_enumeration_reordering(backend):
    monitor = reader.BatteryMonitor(backend)
    monitor.poll()
    backend.enumerate.return_value = [interface(b"other"), interface()]
    assert monitor.poll()[0].path == b"mouse"


def test_stop_skips_hid_queries(backend):
    monitor = reader.BatteryMonitor(backend, should_stop=lambda: True)
    status, result = monitor.poll(request(b"mouse", 500))
    assert not status.connected and not result.success
    backend.device.assert_not_called()
