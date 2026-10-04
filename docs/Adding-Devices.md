# Adding Devices

The app enumerates HID devices with vendor ID `0x33e4`. Mapped product IDs use the protocol selected in `gwolves/protocols.py`. Unknown IDs are probed using `new`, then `old`, battery queries; a valid response is required before reporting a battery level. Experimental `compx` probing is disabled because its response validation and transport have not been established well enough for automatic detection.

Unknown devices can display battery status after a successful probe, but do not expose polling-rate controls. Successful battery reads alone do not establish that configuration writes are compatible.

## Gather evidence

1. Run `gwolves-battery --diagnose` and record the product ID, interface, product string, and connection mode. This only enumerates devices.
2. Close other mouse utilities, then run `gwolves-battery --once` and, if needed, `gwolves-battery --debug` to check the response.
3. Record the model and firmware version, and repeat separately for wired and receiver connections when available.

Do not assume the product string determines the transport: some wired interfaces identify themselves as “Wireless.” The model mapping and product ID take precedence for known devices.

## Add a mapping

Add a product ID and `(model name, protocol)` tuple to `MODELS` in `gwolves/protocols.py` only after verifying the protocol:

```python
0x5807: ("HSK Pro 4K (Wireless)", "new"),
```

Review `supported_polling_rates` in `gwolves/reader.py` when adding capabilities. Confirm the actual receiver and firmware limits before enabling higher rates. Add tests for the mapping, valid and malformed responses, and any capability rule. Validate polling-rate writes and readback on the device before claiming they work.

## Manual experiments

The files under `scripts/` are historical hardware experiments, not the automated test suite. Some send polling-rate or other HID configuration commands, and may target a hardcoded interface or product ID. Read and adapt them before use. `python -m pytest` collects only `tests/` so normal test runs never execute those experiments.
