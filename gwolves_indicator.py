import sys
from gwolves.ui import GWolvesBatteryApp

if __name__ == "__main__":
    app = GWolvesBatteryApp(sys.argv)
    sys.exit(app.exec())
