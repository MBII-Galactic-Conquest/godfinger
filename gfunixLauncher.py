#!/usr/bin/env python3
import os
import sys
import time
import argparse
import subprocess
import glob
import psutil
import json

# MB2 GameData Path

GAMEDATA = "../openjk/" #Path to GameData directory example ../GameData or ../jka/

# Default autorestart duration (in seconds): 24 hours
AUTORESTART_DURATION = 24 * 3600  # 24 hours

# Mapping of server modes to their port numbers and configuration file names.
MODE_SETTINGS = {
    'open': {'port': 29070, 'cfg': 'open-server.cfg'},
    'semi-authentic': {'port': 29071, 'cfg': 'semi-authentic-server.cfg'},
    'duel': {'port': 29072, 'cfg': 'duel-server.cfg'},
    'full-authentic': {'port': 29073, 'cfg': 'full-authentic-server.cfg'},
    'legends': {'port': 29074, 'cfg': 'legends-server.cfg'},
}

# PID file to track the launched server process (for mbiided.*)
PID_FILE = "mbiided.pid"


def load_config():
    """
    Load configuration from godfingerCfg.json if available.
    This can override the autorestart duration and mode settings.
    """
    config_file = "godfingerCfg.json"
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            global AUTORESTART_DURATION
            if "autorestart_24" in config:
                AUTORESTART_DURATION = config["autorestart_24"]
            if "modes" in config:
                # Allow overriding port and cfg for each mode
                for mode, settings in config["modes"].items():
                    if mode in MODE_SETTINGS:
                        MODE_SETTINGS[mode].update(settings)
            print("Configuration loaded from godfingerCfg.json")
        except Exception as e:
            print(f"Error loading config: {e}")


def delete_crash_logs():
    """
    Remove any files with a crash_logs_ prefix to ensure a clean start.
    """
    for log_file in glob.glob("crash_logs_*"):
        try:
            os.remove(log_file)
            print(f"Deleted crash log: {log_file}")
        except Exception as e:
            print(f"Failed to delete {log_file}: {e}")


def kill_existing_processes():
    """
    Kill any running processes that match the pattern 'mbiided' to prevent zombies.
    Only processes owned by the current user will be processed.
    """
    current_uid = os.getuid()  # works on Unix-like systems
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            # Check if process is owned by the current user
            try:
                if proc.uids().real != current_uid:
                    continue
            except (psutil.AccessDenied, AttributeError):
                continue

            if proc.info['name'] and 'mbiided' in proc.info['name']:
                try:
                    proc.terminate()
                    proc.wait(timeout=3)
                except psutil.TimeoutExpired:
                    proc.kill()
            elif proc.info['cmdline'] and any('mbiided' in arg for arg in proc.info['cmdline']):
                try:
                    proc.terminate()
                    proc.wait(timeout=3)
                except psutil.TimeoutExpired:
                    proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue


def kill_existing_monitors(mode):
    """
    Kill any running instances of this script in monitor mode for the given mode.
    """
    current_pid = os.getpid()
    for proc in psutil.process_iter(['pid', 'cmdline']):
        try:
            if proc.pid == current_pid:
                continue
            cmd = proc.info['cmdline']
            if cmd and any("glauncher.py" in part for part in cmd) and "--monitor" in cmd and mode in cmd:
                print(f"Killing existing monitor process PID {proc.pid} for mode {mode}")
                proc.terminate()
                proc.wait(timeout=3)
        except Exception:
            continue


def write_pid(pid):
    """
    Write the process ID of the launched server to a PID file.
    """
    with open(PID_FILE, 'w') as f:
        f.write(str(pid))
    print(f"Written PID {pid} to {PID_FILE}")


def read_pid():
    """
    Read the process ID from the PID file.
    """
    try:
        with open(PID_FILE, 'r') as f:
            return int(f.read().strip())
    except Exception:
        return None


def remove_pid_file():
    """
    Remove the PID file.
    """
    if os.path.exists(PID_FILE):
        os.remove(PID_FILE)
        print(f"Removed PID file {PID_FILE}")


def launch_server(mode):
    """
    Launch the dedicated server in the specified mode.
    The command uses screen to run the server in the background.
    """
    settings = MODE_SETTINGS.get(mode)
    if not settings:
        print(f"Unknown mode: {mode}")
        sys.exit(1)
    port = settings['port']
    cfg_file = settings['cfg']
    session_name = mode.replace(" ", "_")
    command = (
        f"screen -dmS {session_name} {GAMEDATA}./mbiided.i386 "
        f"+set fs_game MBII +set dedicated 2 +set net_port {port} +exec {cfg_file}"
    )
    print(f"Launching server with command: {command}")
    proc = subprocess.Popen(command, shell=True)
    time.sleep(1)  # allow time for the screen session to initialize
    write_pid(proc.pid)
    return proc


def is_server_running(mode):
    """
    Check if a screen session for the given mode is running.
    """
    session_name = mode.replace(" ", "_")
    try:
        result = subprocess.run("screen -ls", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return session_name in result.stdout.decode()
    except Exception:
        return False


def monitor_loop(mode):
    """
    Monitor the server and restart it every AUTORESTART_DURATION seconds.
    Also, if the server dies unexpectedly, launch it immediately.
    This loop runs indefinitely.
    """
    last_restart = time.time()
    while True:
        # If the server is not running, launch it and update the restart timer.
        if not is_server_running(mode):
            print("Server process not running. Restarting...")
            launch_server(mode)
            last_restart = time.time()
            time.sleep(15)  # allow extra time after a restart

        # If it's been AUTORESTART_DURATION seconds since the last restart, then restart.
        if time.time() - last_restart >= AUTORESTART_DURATION:
            print("24 hours elapsed. Restarting server...")
            stop_server(mode)
            launch_server(mode)
            last_restart = time.time()
            time.sleep(15)

        time.sleep(10)


def stop_server(mode):
    """
    Stop the server by terminating the screen session for the given mode.
    Also attempts to clean up the PID file and any leftover processes.
    """
    session_name = mode.replace(" ", "_")
    command = f"screen -S {session_name} -X quit"
    try:
        subprocess.run(command, shell=True, check=True)
        print(f"Screen session '{session_name}' terminated.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to terminate screen session '{session_name}': {e}")

    pid = read_pid()
    if pid and psutil.pid_exists(pid):
        try:
            p = psutil.Process(pid)
            try:
                p.terminate()
                p.wait(timeout=3)
                print(f"Process {pid} terminated.")
            except psutil.TimeoutExpired:
                p.kill()
                print(f"Process {pid} force killed.")
        except Exception as e:
            print(f"Error terminating process {pid}: {e}")
    else:
        print("No process found from PID file.")
    remove_pid_file()
    kill_existing_processes()
    kill_existing_monitors(mode)


def main():
    load_config()

    parser = argparse.ArgumentParser(
        description="MovieBattles 2 Dedicated Server Launcher via godfinger"
    )
    parser.add_argument("mode", choices=list(MODE_SETTINGS.keys()),
                        help="Server mode to launch")
    parser.add_argument("action", choices=["start", "stop", "restart"],
                        help="Action to perform")
    # Hidden flag used internally for monitor processes
    parser.add_argument("--monitor", action="store_true", default=False, help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.monitor:
        # This branch is only used by the monitor process.
        monitor_loop(args.mode)
        sys.exit(0)

    # Normal user actions
    if args.action == "start":
        delete_crash_logs()
        kill_existing_processes()
        kill_existing_monitors(args.mode)
        launch_server(args.mode)
        # Fork off a monitor process so that the server auto-restarts every 24 hours.
        try:
            pid = os.fork()
            if pid > 0:
                print(f"Monitor started in background (PID {pid}).")
                sys.exit(0)
            else:
                # Child process: re-execute this script with the --monitor flag.
                os.execv(sys.executable, [sys.executable] + sys.argv + ["--monitor"])
        except AttributeError:
            # os.fork() not available (e.g. on Windows), run monitor inline.
            monitor_loop(args.mode)
    elif args.action == "stop":
        stop_server(args.mode)
    elif args.action == "restart":
        stop_server(args.mode)
        time.sleep(2)
        delete_crash_logs()
        kill_existing_processes()
        kill_existing_monitors(args.mode)
        launch_server(args.mode)
        try:
            pid = os.fork()
            if pid > 0:
                print(f"Monitor started in background (PID {pid}).")
                sys.exit(0)
            else:
                os.execv(sys.executable, [sys.executable] + sys.argv + ["--monitor"])
        except AttributeError:
            monitor_loop(args.mode)


if __name__ == "__main__":
    main()
