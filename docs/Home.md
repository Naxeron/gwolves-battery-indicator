# G-Wolves Battery Indicator

A Linux tray utility that reads battery percentage, charging state, and polling rate from G-Wolves mice and receivers using reverse-engineered HID protocols.

The app checks status in the background every **5 seconds** by default. Use `--interval` to change this, or Refresh in the tray menu to request an immediate check. It displays low-battery notifications and provides polling-rate controls for mapped devices. Unknown rates remain unknown until the device returns a recognized value.

Known model mappings use the `new` or `old` protocol. Unknown product IDs can be probed for battery support, but do not gain polling-rate controls automatically. The experimental `compx` protocol is excluded from automatic probing. Support depends on the device and firmware; the project does not claim universal compatibility.

- [Installation and commands](../README.md)
- [Troubleshooting](Troubleshooting.md)
- [Protocols](Protocols.md)
- [Adding devices](Adding-Devices.md)
