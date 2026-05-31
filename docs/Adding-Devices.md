# Adding Devices

G-Wolves frequently releases new mice, revisions, and limited editions. To accommodate this, the indicator features **Dynamic Protocol Probing**. 

If a device matches the G-Wolves Vendor ID (`0x33e4`) but its Product ID (PID) is unknown to the app, the background thread will automatically run a test:
1. Probe battery using the `new` protocol.
2. Probe battery using the `old` protocol.
3. Probe battery using the `compx` protocol.

If any of these succeed, the app caches the device PID in memory and treats it accordingly.

## Hardcoding a New Device

For long-term stability and guaranteed correct parsing, you should add newly discovered PIDs directly to the source code:

1. Open `gwolves/protocols.py`.
2. Locate the `MODELS` dictionary.
3. Add a new entry with the correct Hex PID as the key, and a tuple mapping the `(Model Name, Protocol)`:

```python
MODELS = {
    # ...
    0x5807: ("HSK Pro 4K (Wireless)", "new"),
    # ...
}
```

## Polling Rates
Note that polling rate limits are dynamically evaluated based on the product string (e.g. checking if it says "4K" or "8K") or hardcoded PID lists inside `gwolves/device.py`. If a new 4K/8K mouse is added, make sure its PID is added to the supported rates lists in the `BatteryReaderThread.run` method so the user can select up to 4000Hz or 8000Hz.
