#!/usr/bin/env python3
import os
import sys
import shutil

# Color formatting for terminal output
def print_success(msg):
    print(f"\033[92m[✓] {msg}\033[0m")

def print_info(msg):
    print(f"\033[94m[*] {msg}\033[0m")

def print_warning(msg):
    print(f"\033[93m[!] {msg}\033[0m")

def print_error(msg):
    print(f"\033[91m[✗] {msg}\033[0m")

def check_dependencies():
    print_info("Checking python dependencies...")
    all_ok = True
    
    try:
        import hid
        print_success("Dependency 'hidapi' is installed.")
    except ImportError:
        print_warning("Dependency 'hidapi' is missing. You can install it via:")
        print("    pip install hidapi   OR   sudo pacman -S python-hidapi")
        all_ok = False
        
    try:
        from PyQt6 import QtWidgets
        print_success("Dependency 'PyQt6' is installed.")
    except ImportError:
        print_warning("Dependency 'PyQt6' is missing. You can install it via:")
        print("    pip install PyQt6    OR   sudo pacman -S python-pyqt6")
        all_ok = False
        
    return all_ok

def setup_autostart(app_path):
    print_info("Configuring autostart entry...")
    autostart_dir = os.path.expanduser("~/.config/autostart")
    os.makedirs(autostart_dir, exist_ok=True)
    
    desktop_file_path = os.path.join(autostart_dir, "gwolves-battery.desktop")
    
    desktop_content = f"""[Desktop Entry]
Name=G-Wolves Battery Indicator
Comment=System tray battery indicator for G-Wolves mice
Exec={sys.executable} {app_path}
Icon=battery
Terminal=false
Type=Application
Categories=Utility;
StartupNotify=false
"""
    
    try:
        with open(desktop_file_path, "w") as f:
            f.write(desktop_content)
        os.chmod(desktop_file_path, 0o755)
        print_success(f"Autostart entry created at: {desktop_file_path}")
    except Exception as e:
        print_error(f"Failed to create autostart entry: {e}")

def check_udev_rules(rules_src_path):
    print_info("Checking udev rules...")
    dest_rules = "/etc/udev/rules.d/99-gwolves-universal.rules"
    
    if os.path.exists(dest_rules):
        print_success(f"Udev rules file exists at {dest_rules}")
    else:
        print_warning(f"Udev rules file is not installed at {dest_rules}")
        print("\nTo grant permission to access the G-Wolves USB devices without root, run the following commands:")
        print(f"\033[95msudo cp {rules_src_path} {dest_rules}\033[0m")
        print("\033[95msudo udevadm control --reload-rules && sudo udevadm trigger\033[0m\n")

def main():
    print("=" * 60)
    print("      G-Wolves Battery Indicator Universal Generator")
    print("=" * 60)
    
    project_dir = os.path.dirname(os.path.abspath(__file__))
    app_path = os.path.join(project_dir, "app.py")
    rules_src_path = os.path.join(project_dir, "99-gwolves-universal.rules")
    
    if not os.path.exists(app_path):
        print_error(f"Could not find app.py at {app_path}")
        sys.exit(1)
        
    deps_ok = check_dependencies()
    setup_autostart(app_path)
    check_udev_rules(rules_src_path)
    
    print("-" * 60)
    if deps_ok:
        print_success("Setup complete! You can run the widget now using:")
        print(f"    python3 {app_path} &")
    else:
        print_warning("Setup finished but some dependencies are missing. Please install them to run the application.")
    print("=" * 60)

if __name__ == "__main__":
    main()
