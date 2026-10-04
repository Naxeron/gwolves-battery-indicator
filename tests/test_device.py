from threading import Event
from unittest.mock import Mock

import pytest

from gwolves import device
from gwolves.reader import BatteryStatus, RateResult


@pytest.mark.parametrize("interval", [0, -1, float("nan"), float("inf"), 1e300])
def test_worker_rejects_invalid_poll_interval(interval):
    with pytest.raises(ValueError):
        device.BatteryReaderThread(poll_interval=interval)


def test_requests_require_connected_validated_device():
    worker = device.BatteryReaderThread()
    assert not worker.request_polling_rate(500, ())
    worker._status = BatteryStatus(connected=True, supported_rates=(500, 1000),
                                  device_key=(b"mouse", 123, "serial", 1))
    assert not worker.request_polling_rate(8000, worker._status.device_key)
    assert not worker.request_polling_rate(500, (b"old", 123, "serial", 1))
    assert worker.request_polling_rate(500, worker._status.device_key)
    assert not worker.request_polling_rate(1000, worker._status.device_key)
    assert worker._pending.device_key == worker._status.device_key
    worker.stop()
    assert not worker.request_polling_rate(500, worker._status.device_key)


def test_rate_result_emitted_after_status_and_queue_cleared():
    monitor = Mock()
    worker = device.BatteryReaderThread(monitor=monitor)
    status = BatteryStatus(connected=True, supported_rates=(500, 1000),
                           device_key=(b"mouse", 123, "serial", 1))
    worker._status = status
    assert worker.request_polling_rate(500, status.device_key)
    events = []
    worker.status_updated.connect(lambda *args: events.append("status"))
    worker.polling_rate_result.connect(lambda *args: events.append(args))

    def poll(request):
        assert request.rate == 500
        worker.stop()
        return status, RateResult(500, True, "Confirmed")

    monitor.poll.side_effect = poll
    worker.run()
    assert events == ["status", (500, True, "Confirmed")]
    assert worker._pending is None


def test_stop_wakes_worker_with_long_poll_interval():
    polled = Event()
    monitor = Mock()
    monitor.poll.side_effect = lambda request: (polled.set() or BatteryStatus(), None)
    worker = device.BatteryReaderThread(poll_interval=3600, monitor=monitor)
    worker.start()
    try:
        assert polled.wait(2)
        worker.stop()
        assert worker.wait(1000)
    finally:
        worker.stop()
        worker.wait()


def test_refresh_wakes_worker_without_waiting_for_interval():
    polled = Event()
    refreshed = Event()
    monitor = Mock()
    worker = device.BatteryReaderThread(poll_interval=3600, monitor=monitor)

    def poll(request):
        if polled.is_set():
            refreshed.set()
            worker.stop()
        polled.set()
        return BatteryStatus(), None

    monitor.poll.side_effect = poll
    worker.start()
    try:
        assert polled.wait(2)
        worker.trigger_check()
        assert refreshed.wait(2)
        assert worker.wait(1000)
    finally:
        worker.stop()
        worker.wait()


def test_stop_cancels_accepted_request_before_it_reaches_hardware():
    monitor = Mock()
    worker = device.BatteryReaderThread(monitor=monitor)
    worker._status = BatteryStatus(connected=True, supported_rates=(500,), device_key=(b"mouse",))
    assert worker.request_polling_rate(500, worker._status.device_key)
    events = []
    worker.polling_rate_result.connect(lambda *args: events.append(args))
    worker.stop()
    worker.run()
    monitor.poll.assert_not_called()
    assert events == [(500, False, "Application is stopping")]


def test_unexpected_backend_error_fails_request_and_reports_status():
    monitor = Mock()
    worker = device.BatteryReaderThread(monitor=monitor)
    worker._status = BatteryStatus(connected=True, supported_rates=(500,), device_key=(b"mouse",))
    assert worker.request_polling_rate(500, worker._status.device_key)
    results = []
    statuses = []
    worker.polling_rate_result.connect(lambda *args: results.append(args))
    worker.status_updated.connect(statuses.append)

    def fail(request):
        worker.stop()
        raise ValueError("unexpected failure")

    monitor.poll.side_effect = fail
    worker.run()
    assert not statuses[0].connected and "unexpected failure" in statuses[0].error
    assert results == [(500, False, "unexpected failure")]
