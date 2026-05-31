import hid
import time
from PyQt6.QtCore import QThread, pyqtSignal

from gwolves.protocols import VID, MODELS, DYNAMIC_PROTOCOLS, query_battery, query_polling_rate, set_polling_rate

class BatteryReaderThread(QThread):
    # Signals: (percentage, is_charging, is_connected, error_message, model_name, polling_rate, supported_rates)
    status_updated = pyqtSignal(int, bool, bool, str, str, int, list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = True
        self.force_check = False
        self.target_polling_rate = None

    def run(self):
        print("Battery reader background thread started.")
        while self.running:
            dev = None
            try:
                devices = hid.enumerate(VID)
                gw_devices = [d for d in devices if d['vendor_id'] == VID]
                
                if not gw_devices:
                    self.status_updated.emit(0, False, False, "Receiver/Mouse disconnected", "G-Wolves Mouse", 0, [])
                else:
                    opened = False
                    for d in gw_devices:
                        try:
                            dev = hid.device()
                            dev.open_path(d['path'])
                            pid = d['product_id']
                            product_string = d.get('product_string') or "G-Wolves Mouse"
                            
                            is_wireless = any(x in product_string.lower() for x in ["receiver", "dongle", "wireless"])
                            
                            # Lookup or Auto-Detect protocol
                            if pid in MODELS:
                                model_name, protocol = MODELS[pid]
                            elif pid in DYNAMIC_PROTOCOLS:
                                model_name, protocol = DYNAMIC_PROTOCOLS[pid]
                            else:
                                protocol = None
                                for p_test in ["new", "old", "compx"]:
                                    success, _, _, _ = query_battery(dev, p_test, is_wireless)
                                    if success:
                                        protocol = p_test
                                        break
                                if protocol:
                                    model_name = f"G-Wolves {product_string.replace('G-Wolves ', '')} (Probed)"
                                    DYNAMIC_PROTOCOLS[pid] = (model_name, protocol)
                                    print(f"Auto-detected PID {hex(pid)} to use {protocol} protocol.")
                                else:
                                    model_name = f"Unknown G-Wolves ({hex(pid)})"
                                    protocol = "new"  # fallback
                            
                            is_high_rate = False
                            # Determine supported rates based on PID and product string
                            if "8k" in product_string.lower() or "8k" in model_name.lower() or pid in [0x3817, 0x6817, 0x5617, 0x3617, 0x3854, 0x3619]:
                                supported_rates = [125, 250, 500, 1000, 2000, 4000, 8000]
                                is_high_rate = True
                            elif "4k" in product_string.lower() or "4k" in model_name.lower() or pid in [0x5807, 0x5407, 0x5707, 0x5907]:
                                supported_rates = [125, 250, 500, 1000, 2000, 4000]
                                is_high_rate = True
                            else:
                                supported_rates = [125, 250, 500, 1000]
                            
                            # Write pending target rate if set
                            if self.target_polling_rate is not None:
                                if self.target_polling_rate in supported_rates:
                                    set_polling_rate(dev, protocol, is_wireless, self.target_polling_rate, is_high_rate)
                                self.target_polling_rate = None
                            
                            # Query current battery and polling rate
                            success, percentage, is_charging, err = query_battery(dev, protocol, is_wireless)
                            current_rate = query_polling_rate(dev, protocol, is_wireless, is_high_rate) or 1000
                            
                            if success:
                                if is_charging and percentage == 100:
                                    percentage = 99
                                self.status_updated.emit(percentage, is_charging, True, "", model_name, current_rate, supported_rates)
                                opened = True
                                break
                            else:
                                continue
                        except Exception:
                            continue
                        finally:
                            if dev:
                                try:
                                    dev.close()
                                except:
                                    pass
                                dev = None
                                
                    if not opened:
                        self.status_updated.emit(0, False, False, "Permission denied / Device busy", "G-Wolves Mouse", 0, [])
            except Exception as e:
                self.status_updated.emit(0, False, False, f"Error: {str(e)}", "G-Wolves Mouse", 0, [])
            
            # Sleep 5 seconds or until forced / target rate set
            sleep_intervals = 5
            for _ in range(sleep_intervals * 10):
                if not self.running:
                    break
                if self.force_check or self.target_polling_rate is not None:
                    self.force_check = False
                    break
                time.sleep(0.1)

    def trigger_check(self):
        self.force_check = True

    def stop(self):
        self.running = False
