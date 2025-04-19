import os
import time
import psutil

# === CONFIG ===
target_file = "mbiided.x86.exe"
max_depth = 25

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
        
        # Check if the process is running
        if not is_process_running(target_file):
            print(f"[AUTO-START] {target_file} is not running. Launching...")
            os.startfile(full_path)  # Start the file
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
