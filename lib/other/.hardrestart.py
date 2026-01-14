import subprocess
import sys
import os
import time
import psutil # Ensure you have psutil installed: pip install psutil

# --- Configuration ---
# Define the process names to target
MBIIDED_PROCESS_NAME_WIN = "mbiided.x86.exe"
MBIIDED_PROCESS_NAME_LINUX = "mbiided.i386"
GODFINGER_PROCESS_MARKER = "godfinger.py" # Used to find the main Godfinger Python process

# Global wait parameters (can be tuned here if needed)
PROCESS_CHECK_INTERVAL = 1.0 # How often to check for processes in seconds
MAX_PROCESS_WAIT_TIME = 30   # Max time to wait for a process to exit after termination attempt
POST_TERMINATION_GRACE_PERIOD = 5 # Brief pause after all terminations for OS cleanup

# --- Logging Functions ---
# Using print() for guaranteed console output across different environments

def log_info(message):
    """Logs informational messages."""
    print(f"[{time.ctime()}] INFO: {message}")

def log_warning(message):
    """Logs warning messages."""
    print(f"[{time.ctime()}] WARNING: {message}")

def log_error(message):
    """Logs error messages."""
    print(f"[{time.ctime()}] ERROR: {message}")

def log_debug(message):
    """Logs detailed debug messages. Enabled by default for troubleshooting."""
    print(f"[{time.ctime()}] DEBUG: {message}")


# --- Path Helper Function ---

def get_godfinger_app_root_dir():
    """
    Calculates and returns the absolute path to the 'godfinger/' root directory.
    This function assumes hardrestart.py is located at 'godfinger/lib/other/hardrestart.py'.
    """
    # Get the directory of the current script (hardrestart.py)
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    log_debug(f"Current script directory: {current_script_dir}")

    # Go up two levels to reach the 'godfinger/' root
    app_root_dir = os.path.abspath(os.path.join(current_script_dir, '..', '..'))
    log_info(f"Calculated Godfinger application root directory: {app_root_dir}")
    return app_root_dir


# --- Process Termination Logic ---

def terminate_target_process(process_name, cmdline_marker=None, cwd_check_path=None):
    """
    Attempts to find and terminate processes matching the given criteria.
    This function is designed to be robust in identifying specific processes.

    Args:
        process_name (str): The expected base name of the process (e.g., "python", "mbiided.x86.exe").
        cmdline_marker (str, optional): A unique string found in the process's command line
                                        (e.g., "godfinger.py" for Python scripts).
        cwd_check_path (str, optional): An absolute path. If provided, processes will only be targeted
                                        if their Current Working Directory (CWD) is within or contains
                                        this path. Crucial for identifying specific Python scripts.
    Returns:
        bool: True if any target process was found and termination was initiated, False otherwise.
    """
    log_info(f"Attempting to terminate processes: Name='{process_name}', Marker='{cmdline_marker}', CWD Check='{cwd_check_path}'")
    
    terminated_any_process = False
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'status', 'cwd']):
        try:
            current_pid = proc.info['pid']
            current_name = proc.info['name']
            current_cmdline = proc.info['cmdline']
            current_cwd = proc.info['cwd']
            current_status = proc.info['status']

            # Skip hardrestart.py itself to avoid self-termination
            if current_pid == os.getpid():
                log_debug(f"Skipping self-process: PID={current_pid} (this is hardrestart.py).")
                continue
            
            log_debug(f"\n--- Examining process: PID={current_pid}, Name='{current_name}', Status='{current_status}' ---")
            log_debug(f"  Cmdline: {current_cmdline}")
            log_debug(f"  CWD: {current_cwd}")

            # --- Step 1: Check Process Name ---
            is_name_match = False
            target_name_lower = process_name.lower()
            current_name_lower = current_name.lower()

            if current_name_lower == target_name_lower:
                is_name_match = True
                log_debug(f"  Name Check: EXACT match with '{process_name}'.")
            elif sys.platform.startswith('win') and target_name_lower == 'python' and current_name_lower in ['python.exe', 'pythonw.exe']:
                is_name_match = True
                log_debug(f"  Name Check: Flexible Python match with '{process_name}'.")
            else:
                log_debug(f"  Name Check: NO match with '{process_name}'.")

            # --- Step 2: Check Command Line Marker (if provided) ---
            is_cmdline_match = False
            if cmdline_marker and current_cmdline:
                cmdline_str = ' '.join(current_cmdline).lower()
                if cmdline_marker.lower() in cmdline_str:
                    is_cmdline_match = True
                    log_debug(f"  Cmdline Check: Marker '{cmdline_marker}' FOUND in cmdline.")
                else:
                    log_debug(f"  Cmdline Check: Marker '{cmdline_marker}' NOT FOUND in cmdline.")
            else:
                is_cmdline_match = True # If no marker is specified, consider this check passed
                log_debug(f"  Cmdline Check: No marker provided or no cmdline available.")

            # --- Step 3: Check Current Working Directory (CWD) (if provided, especially for Python) ---
            is_cwd_match = True # Assume true if no CWD check is needed or passes
            if cwd_check_path and current_cwd:
                target_abs_cwd = os.path.abspath(cwd_check_path).lower()
                current_abs_cwd = os.path.abspath(current_cwd).lower()

                # Check if process CWD is WITHIN or CONTAINS the target CWD
                # This makes the CWD check more robust against subtle path differences
                if not (current_abs_cwd.startswith(target_abs_cwd) or target_abs_cwd.startswith(current_abs_cwd)):
                    is_cwd_match = False
                    log_debug(f"  CWD Check: NO match. Process CWD: '{current_abs_cwd}', Target CWD: '{target_abs_cwd}'.")
                else:
                    log_debug(f"  CWD Check: MATCHED. Process CWD: '{current_abs_cwd}', Target CWD: '{target_abs_cwd}'.")
            elif cwd_check_path:
                log_debug(f"  CWD Check: Cannot perform CWD check (process CWD not available).")
            else:
                log_debug(f"  CWD Check: Not requested for this termination.")

            # --- Step 4: Final Decision Logic ---
            is_potential_target = False
            if process_name.lower().startswith('python'):
                # For Python processes, we need name, marker, and CWD (if provided) to all match
                if is_name_match and is_cmdline_match and is_cwd_match:
                    is_potential_target = True
                    log_debug(f"  Final Decision: Python process is a POTENTIAL TARGET (all criteria met).")
                else:
                    log_debug(f"  Final Decision: Python process is NOT a target (criteria not met).")
            else:
                # For non-Python processes (like mbiided), name match is usually sufficient
                if is_name_match:
                    is_potential_target = True
                    log_debug(f"  Final Decision: Non-Python process is a POTENTIAL TARGET (name matched).")
                else:
                    log_debug(f"  Final Decision: Non-Python process is NOT a target (name mismatch).")

            # --- Step 5: Ignore Zombie/Stopped Processes ---
            if current_status in [psutil.STATUS_ZOMBIE, psutil.STATUS_STOPPED]:
                log_debug(f"  Final Decision: REJECTED due to process status '{current_status}'.")
                is_potential_target = False # Override if status is problematic

            # --- Step 6: If it's a confirmed target, attempt termination ---
            if is_potential_target:
                log_info(f"  *** IDENTIFIED TARGET PROCESS FOR TERMINATION *** PID: {current_pid}")
                log_info(f"    Name: '{current_name}', Cmdline: '{' '.join(current_cmdline)}', CWD: '{current_cwd}'")
                
                try:
                    p = psutil.Process(current_pid)
                    p.terminate() # Request graceful termination (SIGTERM)
                    p.wait(timeout=5) # Wait up to 5 seconds for it to exit
                    if p.is_running():
                        log_warning(f"    Process {current_name} (PID: {current_pid}) did not terminate gracefully. Attempting to kill...")
                        p.kill() # Forceful termination (SIGKILL)
                        p.wait(timeout=5) # Wait up to 5 more seconds
                    log_info(f"    Termination sequence initiated for PID: {current_pid}.")
                    terminated_any_process = True
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
                    log_error(f"    Error terminating process PID: {current_pid} - {e}")
                except Exception as e:
                    log_error(f"    An unexpected error occurred while closing process PID: {current_pid} - {e}")
            else:
                log_debug(f"  Process PID: {current_pid} is NOT a target for termination.")

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            log_debug(f"Process (PID: {proc.info.get('pid', 'N/A')}) disappeared or became inaccessible during check. Skipping.")
            continue
        except Exception as e:
            log_error(f"An unexpected error occurred while checking process (PID: {proc.info.get('pid', 'N/A')}): {e}")
            continue
            
    return terminated_any_process


def wait_for_process_to_exit(process_name, cmdline_marker=None, cwd_check_path=None, timeout=MAX_PROCESS_WAIT_TIME):
    """
    Waits for a process (or processes) matching the criteria to no longer be running.
    This uses similar logic to terminate_target_process for identification.
    """
    log_info(f"Waiting for '{process_name}' (marker: '{cmdline_marker}') to exit for up to {timeout} seconds...")
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        found_any_target_still_running = False
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'status', 'cwd']):
            try:
                current_pid = proc.info['pid']
                current_name = proc.info['name']
                current_cmdline = proc.info['cmdline']
                current_cwd = proc.info['cwd']
                current_status = proc.info['status']

                # Skip hardrestart.py itself
                if current_pid == os.getpid():
                    continue

                # Re-apply identification logic
                is_name_match = False
                target_name_lower = process_name.lower()
                current_name_lower = current_name.lower()
                if current_name_lower == target_name_lower:
                    is_name_match = True
                elif sys.platform.startswith('win') and target_name_lower == 'python' and current_name_lower in ['python.exe', 'pythonw.exe']:
                    is_name_match = True
                
                is_cmdline_match = False
                if cmdline_marker and current_cmdline:
                    cmdline_str = ' '.join(current_cmdline).lower()
                    if cmdline_marker.lower() in cmdline_str:
                        is_cmdline_match = True
                else:
                    is_cmdline_match = True # No marker provided
                
                is_cwd_match = True
                if cwd_check_path and current_cwd:
                    target_abs_cwd = os.path.abspath(cwd_check_path).lower()
                    current_abs_cwd = os.path.abspath(current_cwd).lower()
                    if not (current_abs_cwd.startswith(target_abs_cwd) or target_abs_cwd.startswith(current_abs_cwd)):
                        is_cwd_match = False
                
                is_still_running_target = False
                if process_name.lower().startswith('python'):
                    if is_name_match and is_cmdline_match and is_cwd_match:
                        is_still_running_target = True
                else:
                    if is_name_match:
                        is_still_running_target = True
                
                if current_status in [psutil.STATUS_ZOMBIE, psutil.STATUS_STOPPED]:
                    is_still_running_target = False

                if is_still_running_target:
                    found_any_target_still_running = True
                    log_debug(f"  Waiting check: Found target still running: PID={current_pid}, Name='{current_name}'")
                    break # Found at least one, so loop again after sleep
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue 
            except Exception as e:
                log_error(f"Error during wait_for_process_to_exit iteration (PID: {proc.info.get('pid', 'N/A')}): {e}")
                continue
        
        if not found_any_target_still_running:
            log_info(f"All target processes ({process_name}, marker: '{cmdline_marker}') have exited.")
            return True # Success, all targets are gone
        
        time.sleep(PROCESS_CHECK_INTERVAL)

    log_warning(f"Timeout: Target processes ({process_name}, marker: '{cmdline_marker}') did not exit within {timeout} seconds.")
    return False # Failed to exit within timeout


# --- Application Launch Logic ---

def launch_quickstart_win(app_root_dir):
    """Launches the Windows quickstart batch script in a new console."""
    script_path = os.path.join(app_root_dir, 'quickstart_win.bat') 
    
    log_info(f"Attempting to run Windows quickstart script: {script_path}")
    log_info(f"Setting working directory for quickstart_win.bat to: {app_root_dir}")

    if not os.path.exists(script_path):
        log_error(f"Windows quickstart script NOT FOUND at: {script_path}. Please verify path.")
        return

    try:
        # Using cmd.exe with /k to keep the console open for debugging.
        # This allows you to see any errors or output from the batch file.
        command_to_run = ['cmd.exe', '/k', script_path] 
        log_info(f"Launching command: {command_to_run}")
        log_info(f"Launching quickstart_win.bat in NEW CONSOLE, CWD: '{app_root_dir}'")
        
        subprocess.Popen(command_to_run, creationflags=subprocess.CREATE_NEW_CONSOLE, cwd=app_root_dir)
        
        log_info("Windows quickstart script launch command sent successfully.")
    except Exception as e:
        log_error(f"Failed to launch Windows quickstart script: {e}")

def launch_quickstart_linux_macOS(app_root_dir):
    """
    Launches the Linux/macOS quickstart shell script.
    Attempts to open a new terminal window, falls back to nohup.
    """
    script_path = os.path.join(app_root_dir, 'quickstart_linux_macOS.sh')
    
    log_info(f"Attempting to run Linux/macOS quickstart script: {script_path}")
    log_info(f"Setting working directory for quickstart_linux_macOS.sh to: {app_root_dir}")

    if not os.path.exists(script_path):
        log_error(f"Linux/macOS quickstart script not found at: {script_path}")
        return

    try:
        # Ensure the script is executable
        os.chmod(script_path, 0o755) 
        
        # Try to launch in a new terminal window (common options)
        terminal_commands = [
            ("gnome-terminal", ["gnome-terminal", "--", script_path]),
            ("xterm", ["xterm", "-e", script_path]),
            ("konsole", ["konsole", "-e", script_path]),
            ("alacritty", ["alacritty", "-e", script_path]),
            ("kitty", ["kitty", script_path]), 
            ("open", ["open", "-a", "Terminal", script_path]) # macOS specific
        ]

        launched_graphical = False
        for term_name, cmd_args in terminal_commands:
            try:
                # Check if the terminal emulator exists
                if subprocess.run(["which", cmd_args[0]], capture_output=True, check=False).returncode == 0:
                    log_info(f"Launching with {term_name}: {' '.join(cmd_args)}, CWD: '{app_root_dir}'")
                    subprocess.Popen(cmd_args, preexec_fn=os.setsid, cwd=app_root_dir)
                    log_info(f"Linux/macOS quickstart script launched successfully with {term_name} in new window.")
                    launched_graphical = True
                    break 
                else:
                    log_debug(f"{term_name} not found or not in PATH, trying next option.")
            except Exception as e:
                log_error(f"Failed to launch with {term_name}: {e}")
        
        # Fallback to nohup if no graphical terminal was found or launched
        if not launched_graphical:
            log_warning("No suitable graphical terminal found. Attempting to run Godfinger directly in background with nohup.")
            try:
                log_info(f"Launching with nohup: nohup bash {script_path} >/dev/null 2>&1 & (CWD: {app_root_dir})")
                subprocess.Popen(["nohup", "bash", script_path, ">/dev/null", "2>&1", "&"], 
                                 preexec_fn=os.setsid, # Detach from parent
                                 shell=True, # Required for redirection and '&'
                                 cwd=app_root_dir)
                log_info("Linux/macOS quickstart script launched successfully with nohup in background.")
            except Exception as e:
                log_error(f"Failed to launch with nohup either: {e}")

    except Exception as e:
        log_error(f"Failed to launch Linux/macOS quickstart script: {e}")


# --- Main Script Execution ---

if __name__ == "__main__":
    log_info("--- hardrestart.py: Script Started ---")
    log_info(f"Current working directory of hardrestart.py: {os.getcwd()}")

    godfinger_root_dir = get_godfinger_app_root_dir()

    # 1. Terminate the mbiided process
    mbiided_name = MBIIDED_PROCESS_NAME_WIN if sys.platform.startswith('win') else MBIIDED_PROCESS_NAME_LINUX
    log_info(f"\nPhase 1: Attempting to terminate mbiided process ({mbiided_name})...")

    mbiided_terminated = terminate_target_process(mbiided_name)
    if mbiided_terminated:
        log_info("Waiting for mbiided process to fully exit...")
        wait_for_process_to_exit(mbiided_name)
    else:
        log_info("mbiided process not found or termination not required.")

    # 2. Terminate the main Godfinger Python process
    log_info(f"\nPhase 2: Attempting to terminate Godfinger Python process (marker: '{GODFINGER_PROCESS_MARKER}')...")
    
    current_os_python_base_name = "python" # This will match python.exe, python3.x etc.
    
    godfinger_terminated = terminate_target_process(
        process_name=current_os_python_base_name, 
        cmdline_marker=GODFINGER_PROCESS_MARKER, 
        cwd_check_path=godfinger_root_dir # Crucial for specific Godfinger identification
    )
    
    if godfinger_terminated:
        log_info("Waiting for Godfinger Python process to fully exit...")
        wait_for_process_to_exit(
            process_name=current_os_python_base_name, 
            cmdline_marker=GODFINGER_PROCESS_MARKER, 
            cwd_check_path=godfinger_root_dir
        )
    else:
        log_info("Godfinger Python process not found or termination not required.")

    # 3. Apply a final grace period for OS resource cleanup
    log_info(f"\nPhase 3: Applying a {POST_TERMINATION_GRACE_PERIOD}s grace period for OS resource cleanup.")
    time.sleep(POST_TERMINATION_GRACE_PERIOD)

    # 4. Run the appropriate quickstart script
    log_info("\nPhase 4: All processes terminated. Initiating Godfinger quickstart.")
    if sys.platform.startswith('win'):
        launch_quickstart_win(godfinger_root_dir)
    else:
        launch_quickstart_linux_macOS(godfinger_root_dir)
            
    log_info("\n--- Godfinger restart procedure completed. Check new console for Godfinger output ---")
    sys.exit(0)