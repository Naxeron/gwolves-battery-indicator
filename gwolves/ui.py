import sys
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtCore import Qt
from PyQt6.QtDBus import QDBusConnection

from gwolves.device import BatteryReaderThread

class GWolvesTrayIcon(QSystemTrayIcon):
    # No scroll events needed
    pass



class GWolvesBatteryApp(QApplication):
    def __init__(self, args):
        super().__init__(args)
        
        self.setApplicationName("G-Wolves Battery Indicator")
        self.setQuitOnLastWindowClosed(False)
        
        # Initialize UI Components
        self.tray = GWolvesTrayIcon(self)
        self.tray.setIcon(self.create_percentage_icon(0, False, False))
        self.tray.setVisible(True)
        
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
        self.polling_actions = {}
        
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
        # Only rebuild the actions if the supported rates have changed to prevent closing the menu during interaction
        current_rates_str = str(self.supported_rates)
        if getattr(self, '_last_built_rates', None) != current_rates_str:
            self.polling_menu.clear()
            self.polling_actions.clear()
            if self.supported_rates:
                for rate in self.supported_rates:
                    action = self.polling_menu.addAction(f"{rate} Hz")
                    action.setCheckable(True)
                    action.triggered.connect(lambda checked, r=rate: self.set_mouse_polling_rate(r))
                    self.polling_actions[rate] = action
            else:
                action = self.polling_menu.addAction("No Device Connected")
                action.setEnabled(False)
            self._last_built_rates = current_rates_str

        # Update checked state
        for rate, action in self.polling_actions.items():
            action.setChecked(rate == self.current_polling_rate)

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
