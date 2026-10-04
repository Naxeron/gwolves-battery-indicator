"""Protocol regressions use simulated HID reports and never open hardware."""

import pytest

from gwolves import protocols


class FakeDevice:
    def __init__(self, response=(), write_result="full", error=None,
                 responses=None, write_results=None):
        self.response = response
        self.write_result = write_result
        self.error = error
        self.responses = iter(responses) if responses is not None else None
        self.write_results = iter(write_results) if write_results is not None else None
        self.writes = []
        self.reads = []

    def send_feature_report(self, report):
        self.writes.append(report)
        if self.error:
            raise self.error
        if self.write_results is not None:
            return next(self.write_results)
        return len(report) if self.write_result == "full" else self.write_result

    def get_feature_report(self, report_id, length):
        self.reads.append((report_id, length))
        return next(self.responses) if self.responses is not None else self.response


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(protocols.time, "sleep", lambda _: None)


def battery_report(protocol, percentage=75, charging=0, shifted=False):
    if protocol == "new":
        payload = [0xA1, 0, 2, 2, 0, 0x83, charging, percentage]
    elif protocol == "old":
        payload = [0xA1, 2, 0x8F, 0, charging, percentage]
    else:
        payload = [4, 0, 0, 0, 0, percentage, charging]
    result = [0] + ([0] if shifted else []) + payload
    return result + [0] * ((17 if protocol == "compx" else 65) - len(result))


def polling_report(protocol, value=1, shifted=False, profile=1):
    payload = (
        [0xA1, 0, 2, 2, 1, 0x80, profile, value]
        if protocol == "new"
        else [0xA1, 2, 0x82, 0, value]
    )
    result = [0] + ([0] if shifted else []) + payload
    return result + [0] * (65 - len(result))


def profile_report(profile=1, shifted=False):
    payload = [0xA1, 0, 2, 1, 0, 0x85, profile]
    result = [0] + ([0] if shifted else []) + payload
    return result + [0] * (65 - len(result))


def polling_device(report, protocol):
    responses = [profile_report(), report] if protocol == "new" else [report]
    return FakeDevice(responses=responses)


@pytest.mark.parametrize("protocol", ["new", "old"])
@pytest.mark.parametrize("shifted", [False, True])
@pytest.mark.parametrize("percentage,charging", [(0, 0), (75, 1), (100, 0)])
def test_battery_accepts_both_response_layouts(protocol, shifted, percentage, charging):
    dev = FakeDevice(battery_report(protocol, percentage, charging, shifted))

    assert protocols.query_battery(dev, protocol, True) == (
        True, percentage, bool(charging), ""
    )
    assert dev.reads == [(0, 65)]


@pytest.mark.parametrize("protocol", ["new", "old", "compx"])
@pytest.mark.parametrize("percentage,charging", [(101, 0), (255, 0), (50, 2), (50, 255)])
def test_battery_rejects_invalid_fields(protocol, percentage, charging):
    dev = FakeDevice(battery_report(protocol, percentage, charging))

    success, value, is_charging, error = protocols.query_battery(dev, protocol, True)

    assert (success, value, is_charging) == (False, 0, False)
    assert error


@pytest.mark.parametrize("protocol", ["new", "old"])
@pytest.mark.parametrize("shifted", [False, True])
@pytest.mark.parametrize(
    "byte,frequency",
    [(8, 125), (4, 250), (2, 500), (1, 1000), (16, 1000),
     (32, 2000), (64, 4000), (128, 8000)],
)
def test_polling_rate_decodes_known_values(protocol, shifted, byte, frequency):
    dev = polling_device(polling_report(protocol, byte, shifted), protocol)

    assert protocols.query_polling_rate(dev, protocol, True) == frequency


@pytest.mark.parametrize("protocol", ["new", "old"])
@pytest.mark.parametrize("byte", [0, 3, 255])
def test_unknown_polling_rate_is_not_reported_as_1000(protocol, byte):
    dev = polling_device(polling_report(protocol, byte), protocol)

    assert protocols.query_polling_rate(dev, protocol, True) is None


@pytest.mark.parametrize("protocol", ["new", "old"])
@pytest.mark.parametrize("operation", ["battery", "polling"])
@pytest.mark.parametrize("shifted", [False, True])
def test_responses_reject_truncation_and_wrong_commands(protocol, operation, shifted):
    report = (
        battery_report(protocol, shifted=shifted)
        if operation == "battery"
        else polling_report(protocol, shifted=shifted)
    )
    query = (
        protocols.query_battery
        if operation == "battery"
        else protocols.query_polling_rate
    )
    last_field = (
        8 if protocol == "new" else 6 if operation == "battery" else 5
    ) + shifted
    for length in range(last_field + 1):
        dev = (
            FakeDevice(report[:length]) if operation == "battery"
            else polling_device(report[:length], protocol)
        )
        result = query(dev, protocol, True)
        if operation == "battery":
            assert result[0] is False
        else:
            assert result is None
    report[(6 if protocol == "new" else 3) + shifted] = 0xFF
    dev = (
        FakeDevice(report) if operation == "battery"
        else polling_device(report, protocol)
    )
    result = query(dev, protocol, True)
    if operation == "battery":
        assert result[0] is False
    else:
        assert result is None


@pytest.mark.parametrize("protocol", ["new", "old", "compx"])
def test_unexpected_report_id_is_not_accepted(protocol):
    report = battery_report(protocol)
    report[0] = 1

    assert protocols.query_battery(FakeDevice(report), protocol, True)[0] is False

    report = polling_report(protocol)
    report[0] = 1
    assert protocols.query_polling_rate(polling_device(report, protocol), protocol, True) is None


@pytest.mark.parametrize("percentage,charging", [(0, 0), (75, 1), (100, 0)])
def test_compx_battery_requires_matching_command(percentage, charging):
    report = battery_report("compx", percentage, charging)
    assert protocols.query_battery(FakeDevice(report), "compx", True) == (
        True, percentage, bool(charging), ""
    )
    report[1] = 0
    assert protocols.query_battery(FakeDevice(report), "compx", True)[0] is False


@pytest.mark.parametrize("length", [0, 9, 10, 16, 18, 65])
def test_compx_rejects_incomplete_or_unexpected_report_size(length):
    report = battery_report("compx")
    report = (report + [0] * length)[:length]

    assert protocols.query_battery(FakeDevice(report), "compx", True)[0] is False


@pytest.mark.parametrize("protocol", ["new", "old", "compx"])
def test_zero_filled_response_is_not_a_battery_reading(protocol):
    report = [0] * (17 if protocol == "compx" else 65)

    assert protocols.query_battery(FakeDevice(report), protocol, True)[0] is False


@pytest.mark.parametrize("protocol", ["new", "old", "compx"])
@pytest.mark.parametrize("write_result", [-1, 0, None, 16, 64])
def test_query_does_not_read_after_failed_or_incomplete_write(protocol, write_result):
    dev = FakeDevice(battery_report(protocol), write_result=write_result)
    assert protocols.query_battery(dev, protocol, True)[0] is False
    assert dev.reads == []

    dev = FakeDevice(polling_report("new"), write_result=write_result)
    assert protocols.query_polling_rate(dev, protocol, True) is None
    assert dev.reads == []


@pytest.mark.parametrize("protocol", ["new", "old"])
@pytest.mark.parametrize("write_result", [-1, 0, None, 64])
def test_setting_polling_rate_requires_full_write(protocol, write_result):
    dev = FakeDevice(
        response=profile_report(),
        write_results=[65, write_result] if protocol == "new" else [write_result],
    )

    assert protocols.set_polling_rate(dev, protocol, True, 1000) is False


@pytest.mark.parametrize("protocol", ["new", "old"])
@pytest.mark.parametrize("wireless", [False, True])
def test_preserves_request_packet_formats(protocol, wireless):
    dev = FakeDevice(response=profile_report())
    protocols.query_battery(dev, protocol, wireless)
    protocols.query_polling_rate(dev, protocol, wireless)
    assert protocols.set_polling_rate(dev, protocol, wireless, 4000) is True

    if protocol == "new":
        prefixes = [
            [0, 0, 0, 2, 2, 0, 0x83],
            [0, 0, 0, 2, 1, 0, 0x85],
            [0, 0, 0, 2, 2, 1, 0x80, 1],
            [0, 0, 0, 2, 1, 0, 0x85],
            [0, 0, 0, 2, 2, 1, 0, 1, 64],
        ]
    else:
        prefixes = [
            [0, 0, 2, 0x8F, int(wireless)],
            [0, 0, 2, 0x82, int(wireless)],
            [0, 0, 2, 2, int(wireless), 64],
        ]
    assert dev.writes == [prefix + [0] * (65 - len(prefix)) for prefix in prefixes]
    assert dev.reads == [(0, 65)] * (4 if protocol == "new" else 2)


@pytest.mark.parametrize("wireless", [False, True])
@pytest.mark.parametrize("profile", [1, 3])
@pytest.mark.parametrize("shifted", [False, True])
def test_new_rate_queries_and_changes_target_active_profile(wireless, profile, shifted):
    dev = FakeDevice(responses=[
        profile_report(profile, shifted),
        polling_report("new", 128, shifted, profile),
        profile_report(profile, shifted),
    ])

    assert protocols.query_polling_rate(dev, "new", wireless) == 8000
    assert protocols.set_polling_rate(dev, "new", wireless, 500) is True
    assert dev.writes[1][7] == profile
    assert dev.writes[3][7:9] == [profile, 2]


@pytest.mark.parametrize("profile", [0, -1, 256])
def test_invalid_active_profile_prevents_polling_query_and_setting(profile):
    dev = FakeDevice(response=profile_report(profile))

    assert protocols.query_polling_rate(dev, "new", False) is None
    assert protocols.set_polling_rate(dev, "new", False, 1000) is False
    assert len(dev.writes) == 2
    assert all(report[6] == 0x85 for report in dev.writes)


@pytest.mark.parametrize("offset,wrong_value", [(0, 1), (1, 0), (4, 2), (6, 0x83)])
def test_unrecognized_profile_response_prevents_rate_write(offset, wrong_value):
    report = profile_report()
    report[offset] = wrong_value
    dev = FakeDevice(response=report)

    assert protocols.set_polling_rate(dev, "new", True, 1000) is False
    assert len(dev.writes) == 1
    assert dev.writes[0][6] == 0x85


@pytest.mark.parametrize("length", range(8))
def test_missing_or_truncated_profile_prevents_rate_write(length):
    dev = FakeDevice(response=profile_report()[:length])

    assert protocols.set_polling_rate(dev, "new", True, 1000) is False
    assert len(dev.writes) == 1
    assert dev.writes[0][6] == 0x85


def test_rate_reply_for_another_profile_is_not_confirmation():
    dev = FakeDevice(responses=[
        profile_report(1), polling_report("new", 128, profile=2),
    ])

    assert protocols.query_polling_rate(dev, "new", False) is None


def test_failed_rate_query_write_after_profile_lookup_does_not_read():
    dev = FakeDevice(response=profile_report(), write_results=[65, 0])

    assert protocols.query_polling_rate(dev, "new", False) is None
    assert dev.reads == [(0, 65)]


@pytest.mark.parametrize("protocol", ["new", "old"])
@pytest.mark.parametrize("frequency", [0, 999, 16000])
def test_unsupported_frequency_never_writes(protocol, frequency):
    dev = FakeDevice()

    assert protocols.set_polling_rate(dev, protocol, True, frequency) is False
    assert dev.writes == []


def test_unsupported_protocol_never_writes():
    dev = FakeDevice()

    assert protocols.query_battery(dev, "unknown", True)[0] is False
    assert protocols.query_polling_rate(dev, "unknown", True) is None
    assert protocols.set_polling_rate(dev, "unknown", True, 1000) is False
    assert dev.writes == []


@pytest.mark.parametrize("protocol", ["new", "old", "compx"])
def test_transport_failure_returns_failure_without_printing(protocol, capsys):
    dev = FakeDevice(error=OSError("disconnected"))

    assert protocols.query_battery(dev, protocol, True) == (False, 0, False, "disconnected")
    assert protocols.query_polling_rate(dev, protocol, True) is None
    assert protocols.set_polling_rate(dev, protocol, True, 1000) is False
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("protocol", ["new", "old", "compx"])
def test_disconnect_between_write_and_read_returns_failure(protocol, monkeypatch):
    dev = FakeDevice()

    def disconnected(*_):
        raise OSError("unplugged while reading")

    monkeypatch.setattr(dev, "get_feature_report", disconnected)

    assert protocols.query_battery(dev, protocol, True) == (
        False, 0, False, "unplugged while reading"
    )
    assert protocols.query_polling_rate(dev, protocol, True) is None


def test_unexpected_programming_errors_are_not_hidden():
    dev = FakeDevice(error=TypeError("programming mistake"))

    with pytest.raises(TypeError, match="programming mistake"):
        protocols.query_battery(dev, "new", True)
    with pytest.raises(TypeError, match="programming mistake"):
        protocols.query_polling_rate(dev, "new", True)
    with pytest.raises(TypeError, match="programming mistake"):
        protocols.set_polling_rate(dev, "new", True, 1000)
