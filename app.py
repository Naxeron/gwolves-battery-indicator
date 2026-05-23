import sys
import os
import time
import hid
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtCore import QTimer, QThread, pyqtSignal, Qt

# G-Wolves Fenrir Pro 8K USB Receiver VID and PID
VID = 0x33e4
PID = 0x3617

class BatteryReaderThread(QThread):
    # Signals to communicate battery state to the main UI thread
    # Signature: (percentage, is_charging, is_connected, error_message)
    status_updated = pyqtSignal(int, bool, bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = True
        self.force_check = False

    def run(self):
        print("Battery reader background thread started.")
        while self.running:
            # 1. Enumerate and open the G-Wolves device
            dev = None
            try:
                devices = hid.enumerate(VID, PID)
                if not devices:
                    self.status_updated.emit(0, False, False, "Receiver disconnected")
                else:
                    # Find and open the receiver device
                    # Usually we open the first available path
                    # We will try opening the device paths
                    opened = False
                    for d in devices:
                        try:
                            dev = hid.device()
                            dev.open_path(d['path'])
                            opened = True
                            break
                        except Exception:
                            # Interface busy or permissions error, try next
                            continue
                    
                    if not opened:
                        self.status_updated.emit(0, False, False, "Permission denied / Device busy")
                    else:
                        # 2. Query the battery level using the New Protocol (0x83)
                        # JS: r[2] = 2, r[3] = 2, r[5] = 131 (0x83)
                        # python-hidapi expects Report ID (0) at index 0, followed by 64 bytes
                        buf = [0] * 65
                        buf[0] = 0     # Report ID
                        buf[3] = 2     # Device ID (wiredMouseDeviceID)
                        buf[4] = 2     # Command Category
                        buf[6] = 0x83  # Command ID: Get Battery
                        
                        dev.send_feature_report(buf)
                        time.sleep(0.1) # short sleep for device processing
                        
                        resp = dev.get_feature_report(0, 65)
                        payload = resp[1:] # skip Report ID byte
                        
                        # Parse the response
                        percentage = 0
                        is_charging = False
                        success = False
                        
                        # Case A: Shifted Response
                        if payload[1] == 161 and payload[4] == 2 and payload[6] == 131:
                            is_charging = (payload[7] == 1)
                            percentage = payload[8]
                            success = True
                        # Case B: Unshifted Response
                        elif payload[0] == 161 and payload[3] == 2 and payload[5] == 131:
                            is_charging = (payload[6] == 1)
                            percentage = payload[7]
                            success = True
                            
                        if success:
                            # Apply the 100% charging UI capping logic from G-Wolves client
                            if is_charging and percentage == 100:
                                percentage = 99
                            self.status_updated.emit(percentage, is_charging, True, "")
                        else:
                            self.status_updated.emit(0, False, True, "Invalid response from device")
                            
            except Exception as e:
                self.status_updated.emit(0, False, False, f"Error: {str(e)}")
            finally:
                if dev:
                    try:
                        dev.close()
                    except Exception:
                        pass
            
            # 3. Sleep until the next check (60 seconds) or if forced
            sleep_intervals = 60
            for _ in range(sleep_intervals * 10):
                if not self.running:
                    break
                if self.force_check:
                    self.force_check = False
                    break
                time.sleep(0.1)

    def trigger_check(self):
        self.force_check = True

    def stop(self):
        self.running = False


class GWolvesBatteryApp(QApplication):
    def __init__(self, args):
        super().__init__(args)
        
        # Set application metadata
        self.setApplicationName("G-Wolves Battery Indicator")
        self.setQuitOnLastWindowClosed(False)
        
        # Initialize UI Components
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self.create_percentage_icon(0, False, False))
        self.tray.setVisible(True)
        
        # Build Context Menu
        self.menu = QMenu()
        self.device_action = self.menu.addAction("Device: G-Wolves Fenrir Pro")
        self.device_action.setEnabled(False)
        self.status_action = self.menu.addAction("Battery: Unknown")
        self.status_action.setEnabled(False)
        self.menu.addSeparator()
        
        self.refresh_action = self.menu.addAction("Refresh")
        self.refresh_action.triggered.connect(self.refresh_battery)
        
        self.menu.addSeparator()
        self.exit_action = self.menu.addAction("Exit")
        self.exit_action.triggered.connect(self.exit_app)
        
        self.tray.setContextMenu(self.menu)
        
        # Notification tracking state
        self.low_battery_notified = False
        
        # Start Background Query Thread
        self.reader_thread = BatteryReaderThread()
        self.reader_thread.status_updated.connect(self.handle_status_update)
        self.reader_thread.start()

    def create_percentage_icon(self, percentage, is_charging, is_connected):
        # Create a 32x32 Pixmap (High DPI tray support)
        pixmap = QPixmap(32, 32)
        pixmap.fill(QColor(0, 0, 0, 0)) # transparent background
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        
        # Determine Color Scheme
        if not is_connected:
            color = QColor("#B0BEC5") # Grey if disconnected
        elif is_charging:
            color = QColor("#00E676") # bright green when charging
        elif percentage < 20:
            color = QColor("#FF5252") # Red if battery low (<20%)
        elif percentage < 50:
            color = QColor("#FFAB40") # Amber if battery medium (<50%)
        else:
            color = QColor("#40C4FF") # light blue / green if good
            
        # Draw the Percentage Number
        font = QFont("Sans-Serif", 16, QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(color)
        
        # Text alignment
        text = str(percentage) if is_connected and percentage > 0 else "?"
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text)
        
        # Draw a tiny battery bar at the bottom
        if is_connected:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            bar_width = int(28 * (percentage / 100.0))
            painter.drawRect(2, 28, bar_width, 3)
            
            # Draw a charging lightning/plus indicator at the top right
            if is_charging:
                painter.setPen(color)
                painter.drawLine(26, 4, 26, 10)
                painter.drawLine(23, 7, 29, 7)
                
        painter.end()
        return QIcon(pixmap)

    def handle_status_update(self, percentage, is_charging, is_connected, error_message):
        if not is_connected:
            self.status_action.setText(f"Status: {error_message}")
            self.tray.setIcon(self.create_percentage_icon(0, False, False))
            self.tray.setToolTip(f"G-Wolves Mouse: {error_message}")
            self.low_battery_notified = False # reset notification when disconnected
        else:
            status_text = "Charging" if is_charging else "Discharging"
            self.status_action.setText(f"Battery: {percentage}% ({status_text})")
            self.tray.setIcon(self.create_percentage_icon(percentage, is_charging, True))
            self.tray.setToolTip(f"G-Wolves Mouse: {percentage}% ({status_text})")
            
            # Send Notification if Battery is Low (< 15%)
            if not is_charging and percentage <= 15:
                if not self.low_battery_notified:
                    self.tray.showMessage(
                        "Low Battery",
                        f"G-Wolves Mouse battery is low: {percentage}%",
                        QSystemTrayIcon.MessageIcon.Warning,
                        5000
                    )
                    self.low_battery_notified = True
            else:
                self.low_battery_notified = False

    def refresh_battery(self):
        self.reader_thread.trigger_check()

    def exit_app(self):
        self.reader_thread.stop()
        self.reader_thread.wait()
        self.quit()

if __name__ == "__main__":
    app = GWolvesBatteryApp(sys.argv)
    sys.exit(app.exec())
