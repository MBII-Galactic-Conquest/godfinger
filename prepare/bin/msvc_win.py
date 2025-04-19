import urllib.request
import winreg
import subprocess
import sys
import os

# You can change this to the redistributable version you're looking for
TARGET_NAME = "Microsoft Visual C++ 2015-2022 Redistributable (x86)"

# Path to local installer if available
LOCAL_INSTALLER_PATH = "vc_redist.x86.exe"

# Download URL from Microsoft (as of 2024)
VC_REDIST_URL = "https://aka.ms/vs/17/release/vc_redist.x86.exe"

def is_vcredist_installed(name):
    # Check both registry locations
    reg_paths = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall")
    ]

    for root, path in reg_paths:
        try:
            with winreg.OpenKey(root, path) as key:
                for i in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        with winreg.OpenKey(key, subkey_name) as subkey:
                            display_name, _ = winreg.QueryValueEx(subkey, "DisplayName")
                            if name in display_name:
                                print(f"Found installed: {display_name}")
                                return True
                    except FileNotFoundError:
                        continue
                    except OSError:
                        continue
        except FileNotFoundError:
            continue
    return False

def download_installer(url, dest_path):
    print(f"Downloading {url}...")
    urllib.request.urlretrieve(url, dest_path)
    print("Download complete.")

def install_vcredist(installer_path):
    print(f"Running installer: {installer_path}")
    try:
        subprocess.run([installer_path, "/install", "/norestart"], check=True)
        print("Installation complete.")
    except subprocess.CalledProcessError as e:
        print(f"Installer failed with exit code {e.returncode}.")
        if e.returncode == 1602:
            print("Installer exited manually by user.")
        sys.exit(1)  # Exit with error status

    # Delete installer after installation
    if os.path.exists(installer_path):
        os.remove(installer_path)
        print("Installer deleted.")

def main():
    if is_vcredist_installed(TARGET_NAME):
        print("Visual C++ Redistributable is already installed.")
    else:
        print("Visual C++ Redistributable is not installed.")
        if not os.path.exists(LOCAL_INSTALLER_PATH):
            download_installer(VC_REDIST_URL, LOCAL_INSTALLER_PATH)
        install_vcredist(LOCAL_INSTALLER_PATH)

    input("Press Enter to exit...")

if __name__ == "__main__":
    main()
