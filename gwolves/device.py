"""Qt worker: serializes HID access and wakes immediately for refresh or shutdown."""

import logging
import math
from threading import Event, Lock, TIMEOUT_MAX

from PyQt6.QtCore import QThread, pyqtSignal

from gwolves.reader import BatteryMonitor, BatteryStatus, RateRequest, RateResult

logger = logging.getLogger(__name__)


class BatteryReaderThread(QThread):
    status_updated = pyqtSignal(object)
    polling_rate_result = pyqtSignal(int, bool, str)

    def __init__(self, parent=None, poll_interval=5.0, monitor=None):
        super().__init__(parent)
        if not math.isfinite(poll_interval) or not 1 <= poll_interval <= TIMEOUT_MAX:
            raise ValueError(f"Poll interval must be between 1 and {TIMEOUT_MAX:g} seconds")
        self.poll_interval = poll_interval
        self._stopping = Event()
        self._wake = Event()
        self._lock = Lock()
        self._pending = None
        self._busy = False
        self._status = BatteryStatus()
        self.monitor = monitor if monitor is not None else BatteryMonitor(
            should_stop=self._stopping.is_set
        )

    def run(self):
        while not self._stopping.is_set():
            # Clear before taking the request so requests arriving during I/O wake
            # the next iteration instead of being lost in the timed wait.
            self._wake.clear()
            with self._lock:
                request = self._pending
                self._pending = None
            try:
                status, result = self.monitor.poll(request)
            except Exception as exc:
                # Keep the worker alive, but retain a traceback for unexpected bugs.
                logger.exception("Unexpected error reading mouse status")
                status = BatteryStatus(error=f"Unexpected device error: {exc}")
                result = (RateResult(request.rate, False, str(exc)) if request else None)
            with self._lock:
                self._status = status
                if request:
                    self._busy = False
            self.status_updated.emit(status)
            if result is not None:
                self.polling_rate_result.emit(result.rate, result.success, result.message)
            if not self._stopping.is_set():
                self._wake.wait(self.poll_interval)

        with self._lock:
            pending = self._pending
            self._pending = None
            self._busy = False
        if pending:
            self.polling_rate_result.emit(pending.rate, False, "Application is stopping")

    def request_polling_rate(self, rate, device_key):
        with self._lock:
            if (self._stopping.is_set() or self._busy or not self._status.connected
                    or device_key != self._status.device_key
                    or rate not in self._status.supported_rates):
                return False
            self._pending = RateRequest(self._status.device_key, rate)
            self._busy = True
        self._wake.set()
        return True

    def trigger_check(self):
        self._wake.set()

    def stop(self):
        self._stopping.set()
        self._wake.set()
