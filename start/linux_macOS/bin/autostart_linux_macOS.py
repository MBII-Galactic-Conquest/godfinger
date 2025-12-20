import os
import time
import psutil
import subprocess
import sys

# === CONFIG ===
target_file = "mbiided.i386"
max_depth = 25

# === Check autostart.cfg ===
def should_autostart():
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'autostart.cfg'))
    
    # Check if autostart.cfg exists, if not create it with '1' as the default value
    if not os.path.exists(config_path):
        print("[AUTO-START] autostart.cfg not found. Creating it with default value (1).")
        try:
            with open(config_path, 'w') as f:
                # Writing comment and default value (1)
                f.write("# This file controls whether the auto-start feature is enabled or disabled.\n")
                f.write("# Value '1' means auto-start is enabled, and value '0' means it is disabled.\n")
                f.write("# Default value is '1'.\n")
                f.write("1\n")  # Default to 1
        except Exception as e:
            print(f"[ERROR] Failed to create autostart.cfg: {e}")
            sys.exit(1)

    # Read the value from the config file
    try:
        with open(config_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('#') or not line:
                    continue
                return line == '1'
    except FileNotFoundError:
        print("[AUTO-START] Failed to read autostart.cfg.")
        return False

    return False

if not should_autostart():
    sys.exit(0)

# Get the current directory
current_dir = os.getcwd()
depth = 0

# Function to check if the process is running
def is_process_running(process_name):
    for proc in psutil.process_iter(['pid', 'name']):
        if process_name.lower() in proc.info['name'].lower():
            return True
    return False

# Loop to search for the file up to max_depth
while depth < max_depth:
    print(f"[AUTO-START] Searching for {target_file} in: {current_dir}")
    if os.path.exists(os.path.join(current_dir, target_file)):
        full_path = os.path.join(current_dir, target_file)
        print(f"[AUTO-START] Found {target_file} at: {full_path}")

        args = [
            full_path,
            "--debug",
            "+set", "g_log", "server.log",
            "+set", "g_logExplicit", "3",
            "+set", "g_logClientInfo", "1",
            "+set", "g_logSync", "4",
            "+set", "com_logChat", "2",
            "+set", "dedicated", "2",
            "+set", "fs_game", "MBII",
            "+exec", "server.cfg",
            "+set", "net_port", "29070"
        ]

        # Check if the process is running
        if not is_process_running(target_file):
            print(f"[AUTO-START] {target_file} is not running. Launching...")
            if os.name == "nt":
                # On Windows, start in a new console
                subprocess.Popen(args, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                # On Unix, run in background detached from terminal
                subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, start_new_session=True)
            time.sleep(5)  # Wait for 5 seconds
        else:
            print(f"[AUTO-START] {target_file} is already running.")
        break

    # Go up one directory
    current_dir = os.path.dirname(current_dir)
    depth += 1

    # If we've reached the root directory, check for depth limit
    if current_dir == os.path.abspath(os.sep):
        print(f"[AUTO-START] {target_file} not found in any parent directories!")
        print(f"[AUTO-START] Ensure godfinger installation is placed in a recursive subdirectory of JKA/GameData for automated starts.")
        break

    # If we've reached the max depth
    if depth >= max_depth:
        print(f"[AUTO-START] Reached max depth ({max_depth}) while searching for {target_file}.")
        break

# If we reach here, file isn't found within the depth limit
if depth >= max_depth:
    print(f"[AUTO-START] Could not find {target_file} after {max_depth} attempts.")
    print(f"[AUTO-START] Ensure godfinger installation is placed in a recursive subdirectory of JKA/GameData for automated starts.")
