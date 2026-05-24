import sys
import os
import time
import hid
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtCore import QTimer, QThread, pyqtSignal, Qt

# G-Wolves USB Vendor ID (Universal for all G-Wolves devices)
VID = 0x33e4

# Database of all known G-Wolves models and their protocols
MODELS = {
    # New Protocol (IsNewProtocol = "1")
    0x3808: ("HTM Plus (Wired)", "new"),
    0x3817: ("HTM Plus (Wireless)", "new"),
    0x6808: ("HSK Pro 2.0 (Wired)", "new"),
    0x6817: ("HSK Pro 2.0 (Wireless)", "new"),
    0x5608: ("HTXU (Wired)", "new"),
    0x5617: ("HTXU (Wireless)", "new"),
    0x3608: ("Fenrir Pro (Wired)", "new"),
    0x3617: ("Fenrir Pro (Wireless)", "new"),
    0x5418: ("HTS Plus (Wired, 3950)", "new"),
    0x3854: ("Receiver (Wireless, 3950/3955)", "new"),
    0x4718: ("Lycan (Wired, 3950)", "new"),
    0x5618: ("HTXU (Wired, 3950)", "new"),
    0x4719: ("Lycan (Wired, 3955)", "new"),
    0x5619: ("HTXU (Wired, 3955)", "new"),
    0x5419: ("HTS Plus (Wired, 3955)", "new"),
    0x3619: ("Fenrir Pro (Wired, 3955)", "new"),
    0x2719: ("HTX Mini (Wired, 3955)", "new"),

    # Old Protocol (IsNewProtocol = "0")
    0x3908: ("VUK (Wired)", "old"),
    0x3917: ("VUK (Wireless)", "old"),
    0x7904: ("HT-S2 (Wired)", "old"),
    0x7913: ("HT-S2 (Wireless)", "old"),
    0x3708: ("Fenir Max (Wired)", "old"),
    0x3717: ("Fenir Max (Wireless)", "old"),
    0x5308: ("HTS Ultra (Wired)", "old"),
    0x5317: ("HTS Ultra (Wireless)", "old"),
    0x7704: ("HTR (Wired)", "old"),
    0x7713: ("HTR (Wireless)", "old"),
    0x3508: ("Fenrir (Wired)", "old"),
    0x3517: ("Fenrir (Wireless)", "old"),
    0x7908: ("HT-S2 Pro (Wired)", "old"),
    0x7917: ("HT-S2 Pro (Wireless)", "old"),
    0x5808: ("HSK Pro (Wired)", "old"),
    0x5817: ("HSK Pro (Wireless)", "old"),
    0x2708: ("HTX Mini (Wired)", "old"),
    0x2717: ("HTX Mini (Wireless)", "old"),
    0x5408: ("HTS Plus (Wired)", "old"),
    0x5417: ("HTS Plus (Wireless)", "old"),
    0x5708: ("HTX (Wired)", "old"),
    0x5717: ("HTX (Wireless)", "old"),
    0x5908: ("HSK Plus (Wired)", "old"),
    0x5917: ("HSK Plus (Wireless)", "old"),
    0x7204: ("HSK Lite (Wired)", "old"),
    0x7203: ("HSK Lite (Wireless)", "old"),
    0x7708: ("HTR Pro (Wired)", "old"),
    0x7717: ("HTR Pro (Wireless)", "old"),
    0x5804: ("HSK Pro ACE (Wired)", "old"),
    0x5803: ("HSK Pro ACE (Wireless)", "old"),
    0x5404: ("HTS Plus ACE (Wired)", "old"),
    0x5403: ("HTS Plus ACE (Wireless)", "old"),
    0x5704: ("HTX ACE (Wired)", "old"),
    0x5703: ("HTX ACE (Wireless)", "old"),
    0x5904: ("HSK Plus ACE (Wired)", "old"),
    0x5903: ("HSK Plus ACE (Wireless)", "old"),
}

# Cache for dynamically detected/probed models: PID -> (model_name, protocol)
DYNAMIC_PROTOCOLS = {}

# Mappings for New/Old Protocols: Frequency (Hz) -> Byte Value
FREQ_TO_BYTE_NEW = {
    125: 8,
    250: 4,
    500: 2,
    1000: 1,
    2000: 32,
    4000: 64,
    8000: 128
}

BYTE_TO_FREQ_NEW = {v: k for k, v in FREQ_TO_BYTE_NEW.items()}
# Normalize 16 to 1000Hz (since some devices use/return 16 for 1000Hz)
BYTE_TO_FREQ_NEW[16] = 1000


def query_polling_rate(dev, protocol, is_wireless):
    """Queries the current polling rate of the G-Wolves device."""
    try:
        if protocol == "new":
            buf = [0] * 65
            buf[0] = 0
            buf[3] = 2
            buf[4] = 2
            buf[5] = 1
            buf[6] = 0x80
            buf[7] = 1 if is_wireless else 2
            
            dev.send_feature_report(buf)
            time.sleep(0.05)
            resp = dev.get_feature_report(0, 65)
            if not resp or len(resp) < 10:
                return None
            
            payload = resp[1:]
            # Unshifted
            if payload[0] == 161 and payload[3] == 2 and payload[5] == 128:
                byte_val = payload[7]
            # Shifted
            elif payload[1] == 161 and payload[4] == 2 and payload[6] == 128:
                byte_val = payload[8]
            else:
                return None
            
            if byte_val == 16:
                byte_val = 1
            return BYTE_TO_FREQ_NEW.get(byte_val, 1000)
            
        elif protocol == "old":
            buf = [0] * 65
            buf[0] = 0
            buf[2] = 2
            buf[3] = 0x82
            
            dev.send_feature_report(buf)
            time.sleep(0.05)
            resp = dev.get_feature_report(0, 65)
            if not resp or len(resp) < 8:
                return None
                
            payload = resp[1:]
            # Unshifted
            if payload[0] == 161 and payload[1] == 2 and payload[2] == 0x82:
                byte_val = payload[4]
            # Shifted
            elif payload[1] == 161 and payload[2] == 2 and payload[3] == 0x82:
                byte_val = payload[5]
            else:
                return None
                
            if byte_val == 16:
                byte_val = 1
            return BYTE_TO_FREQ_NEW.get(byte_val, 1000)
            
    except Exception as e:
        print(f"Error querying polling rate: {e}")
    return None


def set_polling_rate(dev, protocol, is_wireless, freq):
    """Sets the G-Wolves device polling rate."""
    try:
        if protocol == "new":
            byte_val = FREQ_TO_BYTE_NEW.get(freq)
            if not byte_val:
                return False
            buf = [0] * 65
            buf[0] = 0
            buf[3] = 2
            buf[4] = 2
            buf[5] = 1
            buf[6] = 0
            buf[7] = 1 if is_wireless else 2
            buf[8] = byte_val
            
            dev.send_feature_report(buf)
            time.sleep(0.05)
            return True
            
        elif protocol == "old":
            byte_val = FREQ_TO_BYTE_NEW.get(freq)
            if not byte_val:
                return False
            buf = [0] * 65
            buf[0] = 0
            buf[2] = 2
            buf[3] = 2
            buf[4] = 0
            buf[5] = byte_val
            
            dev.send_feature_report(buf)
            time.sleep(0.05)
            return True
            
    except Exception as e:
        print(f"Error setting polling rate: {e}")
    return False


def query_battery(dev, protocol, is_wireless):
    """Sends battery status request and parses responses based on protocol type."""
    try:
        if protocol == "new":
            buf = [0] * 65
            buf[0] = 0
            buf[3] = 2     # wiredMouseDeviceID (typically 2)
            buf[4] = 2     # Command Category
            buf[6] = 0x83  # Command ID: Get Battery
            
            dev.send_feature_report(buf)
            time.sleep(0.1)
            resp = dev.get_feature_report(0, 65)
            if not resp or len(resp) < 10:
                return False, 0, False, "No response"
            
            payload = resp[1:]
            # Case A: Shifted Response
            if payload[1] == 161 and payload[4] == 2 and payload[6] == 131:
                return True, payload[8], (payload[7] == 1), ""
            # Case B: Unshifted Response
            elif payload[0] == 161 and payload[3] == 2 and payload[5] == 131:
                return True, payload[7], (payload[6] == 1), ""
            
        elif protocol == "old":
            buf = [0] * 65
            buf[0] = 0
            buf[2] = 2     # Command Category
            buf[3] = 0x8F  # Command ID: Get Battery
            buf[4] = 1 if is_wireless else 0
            
            dev.send_feature_report(buf)
            time.sleep(0.1)
            resp = dev.get_feature_report(0, 65)
            if not resp or len(resp) < 10:
                return False, 0, False, "No response"
            
            payload = resp[1:]
            # Case A: Shifted Response
            if payload[1] == 161 and payload[2] == 2 and payload[3] == 0x8F:
                return True, payload[6], (payload[5] == 1), ""
            # Case B: Unshifted Response
            elif payload[0] == 161 and payload[1] == 2 and payload[2] == 0x8F:
                return True, payload[5], (payload[4] == 1), ""
                
        elif protocol == "compx":
            buf = [0] * 17
            buf[0] = 0
            buf[1] = 0x04  # Command ID
            
            dev.send_feature_report(buf)
            time.sleep(0.1)
            resp = dev.get_feature_report(0, 17)
            if not resp or len(resp) < 10:
                return False, 0, False, "No response"
            
            payload = resp[1:]
            percentage = payload[5]
            is_charging = (payload[6] == 1)
            if 0 <= percentage <= 100:
                return True, percentage, is_charging, ""
                
    except Exception as e:
        return False, 0, False, str(e)
    return False, 0, False, "Protocol mismatch"


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
                            
                            # Determine supported rates based on PID and product string
                            if "8k" in product_string.lower() or "8k" in model_name.lower() or pid in [0x3817, 0x6817, 0x5617, 0x3617, 0x3854, 0x3619]:
                                supported_rates = [125, 250, 500, 1000, 2000, 4000, 8000]
                            elif "4k" in product_string.lower() or "4k" in model_name.lower() or pid in [0x5807, 0x5407, 0x5707, 0x5907]:
                                supported_rates = [125, 250, 500, 1000, 2000, 4000]
                            else:
                                supported_rates = [125, 250, 500, 1000]
                            
                            # Write pending target rate if set
                            if self.target_polling_rate is not None:
                                if self.target_polling_rate in supported_rates:
                                    set_polling_rate(dev, protocol, is_wireless, self.target_polling_rate)
                                self.target_polling_rate = None
                            
                            # Query current battery and polling rate
                            success, percentage, is_charging, err = query_battery(dev, protocol, is_wireless)
                            current_rate = query_polling_rate(dev, protocol, is_wireless) or 1000
                            
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


class GWolvesTrayIcon(QSystemTrayIcon):
    wheelScrolled = pyqtSignal(int)  # 1 for scroll up, -1 for scroll down

    def event(self, event):
        # Handle wheel events on the tray icon
        if event.type() == event.Type.Wheel:
            delta = event.angleDelta().y()
            if delta > 0:
                self.wheelScrolled.emit(1)
            elif delta < 0:
                self.wheelScrolled.emit(-1)
            return True
        return super().event(event)


class GWolvesBatteryApp(QApplication):
    def __init__(self, args):
        super().__init__(args)
        
        self.setApplicationName("G-Wolves Battery Indicator")
        self.setQuitOnLastWindowClosed(False)
        
        # Initialize UI Components
        self.tray = GWolvesTrayIcon(self)
        self.tray.setIcon(self.create_percentage_icon(0, False, False))
        self.tray.setVisible(True)
        
        # Connect scroll event
        self.tray.wheelScrolled.connect(self.handle_tray_scroll)
        
        # Build Context Menu
        self.menu = QMenu()
        self.device_action = self.menu.addAction("Device: G-Wolves Mouse")
        self.device_action.setEnabled(False)
        self.status_action = self.menu.addAction("Battery: Unknown")
        self.status_action.setEnabled(False)
        self.menu.addSeparator()
        
        # Polling Rate Submenu
        self.polling_menu = QMenu("Mouse Polling Rate")
        self.menu.addMenu(self.polling_menu)
        
        self.menu.addSeparator()
        self.refresh_action = self.menu.addAction("Refresh")
        self.refresh_action.triggered.connect(self.refresh_battery)
        
        self.menu.addSeparator()
        self.exit_action = self.menu.addAction("Exit")
        self.exit_action.triggered.connect(self.exit_app)
        
        self.tray.setContextMenu(self.menu)
        
        self.low_battery_notified = False
        self.current_polling_rate = 1000
        self.supported_rates = [125, 250, 500, 1000]
        
        self.rebuild_polling_menu()
        
        # Start background query thread
        self.reader_thread = BatteryReaderThread()
        self.reader_thread.status_updated.connect(self.handle_status_update)
        self.reader_thread.start()

    def create_percentage_icon(self, percentage, is_charging, is_connected):
        pixmap = QPixmap(32, 32)
        pixmap.fill(QColor(0, 0, 0, 0))
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        
        # Colors
        if not is_connected:
            color = QColor("#B0BEC5")
        elif is_charging:
            color = QColor("#00E676")
        elif percentage < 20:
            color = QColor("#FF5252")
        elif percentage < 50:
            color = QColor("#FFAB40")
        else:
            color = QColor("#40C4FF")
            
        # Draw Text
        font = QFont("Sans-Serif", 16, QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(color)
        
        text = str(percentage) if is_connected and percentage > 0 else "?"
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text)
        
        # Underline battery bar
        if is_connected:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            bar_width = int(28 * (percentage / 100.0))
            painter.drawRect(2, 28, bar_width, 3)
            
            if is_charging:
                painter.setPen(color)
                painter.drawLine(26, 4, 26, 10)
                painter.drawLine(23, 7, 29, 7)
                
        painter.end()
        return QIcon(pixmap)

    def rebuild_polling_menu(self):
        self.polling_menu.clear()
        if self.supported_rates:
            for rate in self.supported_rates:
                action = self.polling_menu.addAction(f"{rate} Hz")
                action.setCheckable(True)
                action.setChecked(rate == self.current_polling_rate)
                action.triggered.connect(lambda checked, r=rate: self.set_mouse_polling_rate(r))
        else:
            action = self.polling_menu.addAction("No Device Connected")
            action.setEnabled(False)

    def set_mouse_polling_rate(self, rate, notify=True):
        if rate == self.current_polling_rate:
            return
        self.reader_thread.target_polling_rate = rate
        self.reader_thread.trigger_check()
        
        if notify:
            self.tray.showMessage(
                "Polling Rate Changed",
                f"Mouse polling rate set to {rate}Hz",
                QSystemTrayIcon.MessageIcon.Information,
                2000
            )

    def handle_tray_scroll(self, direction):
        if not self.supported_rates or self.current_polling_rate not in self.supported_rates:
            return
        
        idx = self.supported_rates.index(self.current_polling_rate)
        if direction > 0:  # Scroll up -> increase rate
            if idx < len(self.supported_rates) - 1:
                new_rate = self.supported_rates[idx + 1]
                self.set_mouse_polling_rate(new_rate)
        elif direction < 0:  # Scroll down -> decrease rate
            if idx > 0:
                new_rate = self.supported_rates[idx - 1]
                self.set_mouse_polling_rate(new_rate)

    def handle_status_update(self, percentage, is_charging, is_connected, error_message, model_name, polling_rate, supported_rates):
        if is_connected:
            self.device_action.setText(f"Device: {model_name}")
            status_text = "Charging" if is_charging else "Discharging"
            self.status_action.setText(f"Battery: {percentage}% ({status_text})")
            self.tray.setIcon(self.create_percentage_icon(percentage, is_charging, True))
            
            rate_suffix = f" | Rate: {polling_rate}Hz" if polling_rate else ""
            self.tray.setToolTip(f"{model_name}: {percentage}% ({status_text}){rate_suffix}")
            
            self.current_polling_rate = polling_rate
            self.supported_rates = supported_rates
            self.rebuild_polling_menu()
            
            if not is_charging and 0 < percentage <= 15:
                if not self.low_battery_notified:
                    self.tray.showMessage(
                        "Low Battery",
                        f"{model_name} battery is low: {percentage}%",
                        QSystemTrayIcon.MessageIcon.Warning,
                        5000
                    )
                    self.low_battery_notified = True
            else:
                self.low_battery_notified = False
        else:
            self.device_action.setText(f"Device: {model_name}")
            self.status_action.setText(f"Status: {error_message}")
            self.tray.setIcon(self.create_percentage_icon(0, False, False))
            self.tray.setToolTip(f"{model_name}: {error_message}")
            self.low_battery_notified = False
            
            self.current_polling_rate = 1000
            self.supported_rates = [125, 250, 500, 1000]
            self.rebuild_polling_menu()

    def refresh_battery(self):
        self.reader_thread.trigger_check()

    def exit_app(self):
        self.reader_thread.stop()
        self.reader_thread.wait()
        self.quit()


if __name__ == "__main__":
    app = GWolvesBatteryApp(sys.argv)
    sys.exit(app.exec())
