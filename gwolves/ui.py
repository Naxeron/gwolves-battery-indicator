import sys
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtCore import pyqtSignal, Qt, pyqtSlot
from PyQt6.QtDBus import QDBusConnection

from gwolves.device import BatteryReaderThread


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
        
        # Register DBus Scroll method listeners for Wayland StatusNotifierItem compatibility
        try:
            QDBusConnection.sessionBus().connect(
                "", "/StatusNotifierItem", "org.kde.StatusNotifierItem", "Scroll", self.handle_dbus_scroll
            )
            QDBusConnection.sessionBus().connect(
                "", "/StatusNotifierItem", "org.freedesktop.StatusNotifierItem", "Scroll", self.handle_dbus_scroll
            )
            print("DBus StatusNotifierItem Scroll listeners registered successfully.")
        except Exception as e:
            print(f"Failed to register DBus Scroll listeners: {e}")

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

    @pyqtSlot(int, str)
    def handle_dbus_scroll(self, delta, orientation="vertical"):
        # Handle scroll event forwarded by the DBus StatusNotifierItem host (e.g. KDE panel)
        try:
            d = int(delta)
            if orientation == "vertical":
                if d > 0:
                    self.handle_tray_scroll(1)
                elif d < 0:
                    self.handle_tray_scroll(-1)
        except Exception as e:
            print(f"Error handling DBus scroll: {e}")

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
