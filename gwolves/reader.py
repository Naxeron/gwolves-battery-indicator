"""Synchronous device access, independent of Qt and testable without hardware."""

from dataclasses import dataclass
import logging

import hid

from gwolves.protocols import (
    MODELS, VID, query_battery, query_polling_rate, set_polling_rate,
)

logger = logging.getLogger(__name__)
HIGH_RATE_8K = {0x3817, 0x6817, 0x5617, 0x3617, 0x3854, 0x3619}
HIGH_RATE_4K = {0x5807, 0x5407, 0x5707, 0x5907}


def device_key(info):
    """Bind queued writes to the path AND the enumerated physical device."""
    return (info["path"], info["product_id"], info.get("serial_number") or "",
            info.get("release_number"))


def device_is_wireless(info, model_name):
    # Wired mice can still advertise a product name containing 'Wireless'.
    if info["product_id"] in MODELS:
        return "(Wireless" in model_name
    return any(word in (info.get("product_string") or "").lower()
               for word in ("wireless", "receiver", "dongle"))


def supported_polling_rates(info, model_name, protocol):
    # A battery probe alone is not enough evidence to enable configuration writes.
    if info["product_id"] not in MODELS or protocol not in ("new", "old"):
        return ()
    name = f"{info.get('product_string') or ''} {model_name}".lower()
    rates = (125, 250, 500, 1000)
    if "8k" in name or info["product_id"] in HIGH_RATE_8K:
        return rates + (2000, 4000, 8000)
    if "4k" in name or info["product_id"] in HIGH_RATE_4K:
        return rates + (2000, 4000)
    return rates


@dataclass(frozen=True)
class BatteryStatus:
    percentage: int = 0
    charging: bool = False
    connected: bool = False
    error: str = "Receiver/Mouse disconnected"
    model: str = "G-Wolves Mouse"
    polling_rate: int = 0
    supported_rates: tuple = ()
    path: bytes | str | None = None
    protocol: str | None = None
    device_key: tuple = ()

    def signal_args(self):
        return (self.percentage, self.charging, self.connected, self.error,
                self.model, self.polling_rate, list(self.supported_rates))


@dataclass(frozen=True)
class RateRequest:
    device_key: tuple
    rate: int


@dataclass(frozen=True)
class RateResult:
    rate: int
    success: bool
    message: str


class BatteryMonitor:
    """Find one responsive mouse, retaining its interface until it disconnects."""

    def __init__(self, backend=None, should_stop=None):
        self.backend = backend if backend is not None else hid
        self.should_stop = should_stop or (lambda: False)
        self._preferred = None
        self._protocols = {}

    def _interfaces(self):
        interfaces = [item for item in self.backend.enumerate(VID)
                      if item["vendor_id"] == VID]
        # Enumeration can list the same hidraw path once for each HID collection.
        interfaces.sort(key=lambda item: (
            device_key(item) != self._preferred,
            (item.get("usage_page") or 0) < 0xFF00,
        ))
        unique = {}
        for item in interfaces:
            unique.setdefault(item["path"], item)
        live_keys = {device_key(item) for item in unique.values()}
        self._protocols = {key: value for key, value in self._protocols.items()
                           if key in live_keys}
        return list(unique.values())

    def _battery(self, dev, info):
        pid = info["product_id"]
        model, protocol = MODELS.get(pid, (info.get("product_string") or
                                          f"Unknown G-Wolves ({pid:#06x})", None))
        wireless = device_is_wireless(info, model)
        if protocol:
            return model, protocol, wireless, query_battery(dev, protocol, wireless)
        key = device_key(info)
        cached = self._protocols.get(key)
        protocols = list(dict.fromkeys([cached, "new", "old"]))
        result = (False, 0, False, "No supported protocol responded")
        for candidate in protocols:
            if candidate is None or self.should_stop():
                continue
            result = query_battery(dev, candidate, wireless)
            if result[0]:
                self._protocols[key] = candidate
                return f"{model} (Probed)", candidate, wireless, result
        self._protocols.pop(key, None)
        return model, None, wireless, result

    def poll(self, request=None):
        """Read status; any requested write must pass validation and readback."""
        result = (RateResult(request.rate, False, "Selected mouse is no longer available")
                  if request else None)
        try:
            interfaces = self._interfaces()
        except (OSError, RuntimeError) as exc:
            return BatteryStatus(error=f"USB enumeration failed: {exc}"), result
        if not interfaces:
            self._preferred = None
            return BatteryStatus(), result

        if request:
            interfaces.sort(key=lambda item: device_key(item) != request.device_key)
        errors = []
        for info in interfaces:
            if self.should_stop():
                break
            dev = None
            try:
                dev = self.backend.device()
                dev.open_path(info["path"])
                model, protocol, wireless, battery = self._battery(dev, info)
                success, percentage, charging, error = battery
                if not success:
                    errors.append(error)
                    continue
                rates = supported_polling_rates(info, model, protocol)
                high_rate = bool(rates and rates[-1] > 1000)
                write_ok = False
                selected = request and device_key(info) == request.device_key
                if selected:
                    if self.should_stop():
                        result = RateResult(request.rate, False, "Application is stopping")
                    elif request.rate not in rates:
                        result = RateResult(request.rate, False, "Polling rate is not supported by this device")
                    else:
                        write_ok = set_polling_rate(dev, protocol, wireless, request.rate, high_rate)
                        result = RateResult(request.rate, False, "Device rejected the polling-rate write")
                rate = query_polling_rate(dev, protocol, wireless, high_rate) or 0
                if selected and write_ok:
                    confirmed = rate == request.rate
                    message = (f"Mouse polling rate set to {rate} Hz" if confirmed else
                               "Polling-rate change could not be confirmed; refresh to check the device")
                    result = RateResult(request.rate, confirmed, message)
                self._preferred = device_key(info)
                status = BatteryStatus(percentage, charging, True, "", model, rate,
                                       rates, info["path"], protocol, device_key(info))
                return status, result
            except (OSError, RuntimeError) as exc:
                errors.append(str(exc))
                logger.debug("Cannot query HID interface %r", info["path"], exc_info=True)
            finally:
                if dev is not None:
                    try:
                        dev.close()
                    except (OSError, RuntimeError):
                        logger.debug("Cannot close HID interface", exc_info=True)

        detail = "; ".join(dict.fromkeys(errors)) or "Mouse query interrupted"
        return BatteryStatus(error=f"No responsive mouse: {detail}"), result
