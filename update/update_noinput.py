import os
import time
import threading
import zipfile
import requests
import subprocess
import platform
import shutil
import sys
import json

# Repository details
REPO_URL = "https://github.com/MBII-Galactic-Conquest/godfinger"
REPO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../")
CFG_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "commit.cfg")
COMMIT_ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "commit.env")
UPDATE_DIR = os.path.dirname(os.path.abspath(__file__))
UPDATE_CFG_FILE = os.path.join(UPDATE_DIR, "updateCfg.json")

# Directory for extracting 7z files
EXTRACT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../temp")
SEVEN_PLUGINDIR = os.path.dirname(os.path.abspath(__file__))
SEVEN_ZIP_EXECUTABLE = os.path.join(EXTRACT_DIR, '7-ZipPortable', 'App', '7-Zip', '7z.exe')
SEVEN_ZIP_ARCHIVE = os.path.join(SEVEN_PLUGINDIR, "../lib/other/win/7z_portable.zip")
GIT_ARCHIVE = "PortableGit-2.48.1-64-bit.7z.exe"
GIT_URL = "https://github.com/git-for-windows/git/releases/download/v2.48.1.windows.1/PortableGit-2.48.1-64-bit.7z.exe"

# Get branch name from updateCfg.json (create file with default 'main' if not present)
def get_branch_name():
    if os.path.exists(UPDATE_CFG_FILE):
        try:
            with open(UPDATE_CFG_FILE, 'r') as file:
                config = json.load(file)
                # Ensure the 'branch_name' key is in the JSON
                if "branch_name" in config:
                    return config["branch_name"]
                else:
                    print(f"[INFO] 'branch_name' not found in {UPDATE_CFG_FILE}, setting to 'main'.")
                    config["branch_name"] = "main"
                    save_update_cfg(config)
                    return "main"
        except (json.JSONDecodeError, KeyError) as e:
            print(f"[ERROR] Failed to read {UPDATE_CFG_FILE}. Error: {e}")
            exit(1)
    else:
        print(f"[INFO] {UPDATE_CFG_FILE} not found, creating with 'main' as the default branch.")
        config = {"branch_name": "main"}
        save_update_cfg(config)
        return "main"

# Save the updated config to the JSON file
def save_update_cfg(config):
    try:
        with open(UPDATE_CFG_FILE, 'w') as file:
            json.dump(config, file, indent=4)
            print(f"[INFO] {UPDATE_CFG_FILE} generated with branch_name: {config['branch_name']}")
    except IOError as e:
        print(f"[ERROR] Failed to save {UPDATE_CFG_FILE}: {e}")
        exit(1)

# Directory paths and settings
BRANCH_NAME = get_branch_name()

# Check if the system is Windows
if os.name == 'nt':  # Windows
    GIT_PATH = shutil.which("git")

    if GIT_PATH is None:
        # If Git is not found, check a fallback directory
        GIT_PATH = os.path.abspath(os.path.join("..", "venv", "GIT", "bin"))
        GIT_EXECUTABLE = os.path.abspath(os.path.join(GIT_PATH, "git.exe"))
    else:
        GIT_EXECUTABLE = os.path.abspath(GIT_PATH)

    PYTHON_CMD = shutil.which("python3") if shutil.which("python3") else "python"  # On Windows, just use 'python'

    # Set the environment variables for Windows if Git was found
    if GIT_EXECUTABLE:
        os.environ["GIT_PYTHON_GIT_EXECUTABLE"] = GIT_EXECUTABLE
        #print(f"Git executable set to: {GIT_EXECUTABLE}")
    else:
        print("Git executable could not be set. Ensure Git is installed.")

else:  # Non-Windows (Linux, macOS)
    # Get the default Git executable path
    GIT_EXECUTABLE = shutil.which("git")
    PYTHON_CMD = "python3" if shutil.which("python3") else "python"

    if GIT_EXECUTABLE:
        os.environ["GIT_PYTHON_GIT_EXECUTABLE"] = GIT_EXECUTABLE
        #print(f"Git executable set to default path: {GIT_EXECUTABLE}")
    else:
        print("Git executable not found on the system.")

# Function to check if Git is installed
def check_git_installed():
    global GIT_EXECUTABLE
    if shutil.which("git") or os.path.exists(GIT_EXECUTABLE):
        try:
            subprocess.run([GIT_EXECUTABLE, "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            print("[INFO] Git is installed.")
            return True
        except subprocess.CalledProcessError:
            print("[ERROR] Git version check failed.")
            return False
    else:
        print("[ERROR] Git is not installed.")
        
        if platform.system() in ["Linux", "Darwin"]:
            print("You will have to install Git manually on UNIX. Visit: https://git-scm.com/downloads")
            input("Press Enter to exit...")
            exit(0)
        else:
            install_choice = input("Do you wish to install Git Portable in your virtual environment? (400mb~) (Y/N): ").strip().lower()
            if install_choice == 'y':
                GIT_PATH = os.path.abspath(os.path.join("..", "venv", "GIT", "bin"))
                GIT_EXECUTABLE = os.path.abspath(os.path.join("..", "venv", "GIT", "bin", "git.exe"))
                os.environ["GIT_PYTHON_GIT_EXECUTABLE"] = GIT_EXECUTABLE
                os.environ["PATH"] = os.path.dirname(GIT_PATH) + ";" + os.environ["PATH"]
            return False
            if install_choice != 'y':
                print("You will have to install Git manually. Visit: https://git-scm.com/downloads")
                input("Press Enter to exit...")
                exit(0)
            return False

# Function to download the Git archive (PortableGit)
def download_git():
    print("[DOWNLOAD] Downloading PortableGit archive...")
    response = requests.get(GIT_URL)
    if response.status_code == 200:
        git_archive_path = os.path.join(EXTRACT_DIR, GIT_ARCHIVE)
        with open(git_archive_path, 'wb') as f:
            f.write(response.content)
        print(f"[DOWNLOAD] Successfully downloaded {GIT_ARCHIVE}")
        return git_archive_path
    else:
        print(f"[ERROR] Failed to download {GIT_ARCHIVE} from {GIT_URL}")
        return None

# Function to extract PortableGit using 7-Zip
def extract_git(git_archive_path):
    print(f"[EXTRACT] Extracting {git_archive_path} to ../venv/GIT...")
    extract_dir = os.path.abspath(os.path.join("..", "venv", "GIT"))
    os.makedirs(extract_dir, exist_ok=True)

    try:
        subprocess.run([SEVEN_ZIP_EXECUTABLE, "x", git_archive_path, f"-o{extract_dir}", "-aoa"], 
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("[EXTRACT] Extraction complete.")
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Failed to extract Git: {e}")
        return False
    return True

# Extract 7z Portable
def extract_7z():
    print(f"[EXTRACT] Extracting {SEVEN_ZIP_ARCHIVE}...")
    os.makedirs(EXTRACT_DIR, exist_ok=True)
    with zipfile.ZipFile(SEVEN_ZIP_ARCHIVE, 'r') as zip_ref:
        zip_ref.extractall(EXTRACT_DIR)
    print("[EXTRACT] Extraction complete.")

def start():
    # Prompt user for update
    user_choice = input("Do you wish to check for Godfinger updates? (Y/N): ").strip().lower()
    if user_choice != 'y':
        exit(0)  # Exit if the user does not want to update

    # Ask if they want to grab the latest HEAD for the specified branch
    grab_head = input(f"Do you wish to grab the latest HEAD for the branch '{BRANCH_NAME}'? (Y/N): ").strip().lower()

    if grab_head == 'y':
        # User wants the latest HEAD, so set commit_hash to None to fetch the latest HEAD
        commit_hash = None
    else:
        # If user chooses N, we ask them for a specific commit hash or use commit.env logic
        commit_hash = input("\nEnter the 7-character commit hash you want to grab (or press Enter to use commit.env): ").strip()
        if not commit_hash:
            # If the user doesn't provide a commit hash, check if commit.env has a valid one
            if os.path.exists(COMMIT_ENV_FILE):
                with open(COMMIT_ENV_FILE, 'r') as file:
                    stored_commit_hash = file.read().strip()
                    if len(stored_commit_hash) == 7:  # Ensure it's a valid 7-character commit hash
                        commit_hash = stored_commit_hash
                    else:
                        print("[INFO] Invalid commit hash in commit.env, using latest HEAD.")
                        commit_hash = None
            else:
                print(f"[INFO] {COMMIT_ENV_FILE} not found. Will use the latest HEAD.")
                with open(COMMIT_ENV_FILE, 'w') as file:
                    file.write("")
                print(f"[INFO] {COMMIT_ENV_FILE} successfully created.")
                commit_hash = None
    return commit_hash

# Function to clone the repository if it doesn't exist
def clone_repo_if_needed():
    if os.path.isdir(os.path.join(REPO_PATH, ".git")):
        print("[GITHUB] Repo exists.")
        return
    print("[GITHUB] Cloning repository...")
    subprocess.run([GIT_EXECUTABLE, "clone", "--branch", BRANCH_NAME, REPO_URL, REPO_PATH], check=True)

# Sync repository (force update to latest commit)
def sync_repo(commit_hash=None):
    print("[GITHUB] Fetching latest changes...")
    try:
        subprocess.run([GIT_EXECUTABLE, "fetch", "--all"], check=True)
        subprocess.run([GIT_EXECUTABLE, "reset", "--hard", f"origin/{BRANCH_NAME}"], check=True)
        subprocess.run([GIT_EXECUTABLE, "pull", "origin", BRANCH_NAME], check=True)

        # Disable detached HEAD advice (suppress warning)
        subprocess.run([GIT_EXECUTABLE, "config", "advice.detachedHead", "false"], check=True)

        # If commit_hash is None, grab latest HEAD, else, grab specific commit
        if commit_hash == None:
            print("[GITHUB] Repository is now synced to latest HEAD.")
            commit_hash = subprocess.run(
                [GIT_EXECUTABLE, "rev-parse", "HEAD"], check=True, stdout=subprocess.PIPE, text=True
            ).stdout.strip()
        else:
            print(f"[GITHUB] Checking out commit {commit_hash} ...")
            subprocess.run([GIT_EXECUTABLE, "checkout", commit_hash], check=True)

        # Write commit hash to commit.cfg
        print(f"[GITHUB] Current hash written to {CFG_FILE_PATH} ...")
        with open(CFG_FILE_PATH, "w") as f:
            f.write(commit_hash)

    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Git sync failed: {e}")

# Function to delete temporary files
def remove_temp_files():
    if os.path.exists(EXTRACT_DIR):
        shutil.rmtree(EXTRACT_DIR, ignore_errors=True)
        print("[CLEANUP] Temporary files removed.")

# Main script execution
if __name__ == "__main__":
    commit_hash = start()
    if check_git_installed():
        clone_repo_if_needed()
        sync_repo(commit_hash)
    else:
        print("[INFO] Using 7-Zip Portable to extract Git...")
        extract_7z()
        git_archive_path = download_git()
        if git_archive_path:
            extract_git(git_archive_path)

        clone_repo_if_needed()
        sync_repo(commit_hash)
        remove_temp_files()

    print("\n\n[IMPORTANT] IF you encounter errors after updates, check fallback configs internally in godfinger and all plugins...\n\n")
    input("Press Enter to exit...");
    exit(0);
