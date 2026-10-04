from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QFontMetrics
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtCore import Qt

from gwolves.device import BatteryReaderThread


class GWolvesBatteryApp(QApplication):
    def __init__(self, args, poll_interval=5.0):
        super().__init__(args)

        self.setApplicationName("G-Wolves Battery Indicator")
        self.setQuitOnLastWindowClosed(False)

        # Initialize UI Components
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self.create_percentage_icon(0, False, False))
        self.tray.setToolTip("G-Wolves Mouse: Waiting for device")
        self.tray.setVisible(True)

        # Build Context Menu
        self.menu = QMenu()
        self.device_action = self.menu.addAction("Device: G-Wolves Mouse")
        self.device_action.setEnabled(False)
        self.status_action = self.menu.addAction("Battery: Unknown")
        self.status_action.setEnabled(False)
        self.menu.addSeparator()

        # Polling Rate Submenu
        self.polling_menu = QMenu("Mouse Polling Rate", self.menu)
        self.menu.addMenu(self.polling_menu)

        self.menu.addSeparator()
        self.refresh_action = self.menu.addAction("Refresh")
        self.refresh_action.triggered.connect(self.refresh_battery)

        self.menu.addSeparator()
        self.exit_action = self.menu.addAction("Exit")
        self.exit_action.triggered.connect(self.exit_app)

        self.tray.setContextMenu(self.menu)

        self.low_battery_notified = False
        self.current_device_key = ()
        self.current_polling_rate = 0
        self.supported_rates = []
        self.polling_actions = {}
        self.pending_polling_rate = None
        self._notify_rate_change = True
        self._reader_stopped = False

        self.rebuild_polling_menu()

        # Start background query thread
        self.reader_thread = BatteryReaderThread(self, poll_interval=poll_interval)
        self.reader_thread.status_updated.connect(self.handle_snapshot)
        self.reader_thread.polling_rate_result.connect(self.handle_polling_rate_result)
        self.aboutToQuit.connect(self.stop_reader)
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

        text = str(percentage) if is_connected else "?"
        font = QFont("Sans-Serif", 16, QFont.Weight.Bold)
        font.setPixelSize(22)
        text_width = QFontMetrics(font).horizontalAdvance(text)
        if text_width > 28:
            font.setPixelSize(int(22 * 28 / text_width))
        painter.setFont(font)
        painter.setPen(color)
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
        # Keep actions alive during status refreshes while the menu is open.
        current_rates = tuple(self.supported_rates)
        if getattr(self, '_last_built_rates', None) != current_rates:
            self.polling_menu.clear()
            self.polling_actions.clear()
            for rate in self.supported_rates:
                action = self.polling_menu.addAction(f"{rate} Hz")
                action.setCheckable(True)
                action.triggered.connect(lambda checked, r=rate: self.set_mouse_polling_rate(r))
                self.polling_actions[rate] = action
            self._last_built_rates = current_rates

        pending = self.pending_polling_rate is not None
        title = (
            f"Mouse Polling Rate (applying {self.pending_polling_rate} Hz…)"
            if pending else "Mouse Polling Rate"
        )
        self.polling_menu.setTitle(title)
        self.polling_menu.setEnabled(bool(self.supported_rates) and not pending)
        for rate, action in self.polling_actions.items():
            action.setChecked(rate == self.current_polling_rate)

    def set_mouse_polling_rate(self, rate, notify=True):
        if (
            self.pending_polling_rate is not None
            or rate == self.current_polling_rate
            or rate not in self.supported_rates
        ):
            self.rebuild_polling_menu()
            return
        if not self.reader_thread.request_polling_rate(rate, self.current_device_key):
            self.rebuild_polling_menu()
            if notify:
                self.tray.showMessage(
                    "Polling Rate Not Changed",
                    "The device is unavailable or busy. Refresh and try again.",
                    QSystemTrayIcon.MessageIcon.Warning,
                    5000,
                )
            return
        self.pending_polling_rate = rate
        self._notify_rate_change = notify
        self.rebuild_polling_menu()

    def handle_polling_rate_result(self, rate, success, message):
        if rate != self.pending_polling_rate:
            return
        self.pending_polling_rate = None
        self.rebuild_polling_menu()
        if self._notify_rate_change:
            self.tray.showMessage(
                "Polling Rate Changed" if success else "Polling Rate Not Changed",
                f"Mouse polling rate set to {rate} Hz" if success else message,
                (
                    QSystemTrayIcon.MessageIcon.Information
                    if success else QSystemTrayIcon.MessageIcon.Warning
                ),
                2000 if success else 5000,
            )

    def handle_snapshot(self, status):
        self.current_device_key = status.device_key
        self.handle_status_update(*status.signal_args())

    def handle_status_update(
        self, percentage, is_charging, is_connected, error_message,
        model_name, polling_rate, supported_rates,
    ):
        if is_connected:
            self.device_action.setText(f"Device: {model_name}")
            status_text = "Charging" if is_charging else "Discharging"
            self.status_action.setText(f"Battery: {percentage}% ({status_text})")
            self.tray.setIcon(self.create_percentage_icon(percentage, is_charging, True))

            rate_label = f"{polling_rate} Hz" if polling_rate else "Unknown"
            rate_suffix = f" | Rate: {rate_label}"
            self.tray.setToolTip(f"{model_name}: {percentage}% ({status_text}){rate_suffix}")

            self.current_polling_rate = polling_rate
            self.supported_rates = list(supported_rates)
            self.rebuild_polling_menu()

            if not is_charging and 0 <= percentage <= 15:
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
            self.current_device_key = ()
            self.device_action.setText(f"Device: {model_name}")
            self.status_action.setText(f"Status: {error_message}")
            self.tray.setIcon(self.create_percentage_icon(0, False, False))
            self.tray.setToolTip(f"{model_name}: {error_message}")
            self.low_battery_notified = False

            self.current_polling_rate = 0
            self.supported_rates = []
            self.rebuild_polling_menu()

    def refresh_battery(self):
        self.reader_thread.trigger_check()

    def stop_reader(self):
        """Join the worker before Qt destroys it, whichever path exits the app."""
        if self._reader_stopped:
            return
        self._reader_stopped = True
        self.reader_thread.stop()
        self.reader_thread.wait()

    def exit_app(self):
        self.stop_reader()
        self.quit()
