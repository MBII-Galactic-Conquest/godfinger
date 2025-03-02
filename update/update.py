import os
import time
import threading
import zipfile
import requests
import subprocess
import platform
import shutil
import sys

# Define Git executable path inside virtual environment
GIT_PATH = os.path.abspath(os.path.join("..", "venv", "GIT", "bin"))
GIT_EXECUTABLE = os.path.abspath(os.path.join("..", "venv", "GIT", "bin", "git.exe"))
os.environ["GIT_PYTHON_GIT_EXECUTABLE"] = GIT_EXECUTABLE
os.environ["PATH"] = os.path.dirname(GIT_PATH) + ";" + os.environ["PATH"]

# Repository details
REPO_URL = "https://github.com/MBII-Galactic-Conquest/godfinger"
REPO_PATH = "../"
BRANCH_NAME = "dev"
CFG_FILE_PATH = "commit.cfg"

# Directory for extracting 7z files
EXTRACT_DIR = "../temp"
SEVEN_ZIP_EXECUTABLE = os.path.join(EXTRACT_DIR, '7-ZipPortable', 'App', '7-Zip', '7z.exe')
SEVEN_ZIP_ARCHIVE = "../lib/other/win/7z_portable.zip"
GIT_ARCHIVE = "PortableGit-2.48.1-64-bit.7z.exe"
GIT_URL = "https://github.com/git-for-windows/git/releases/download/v2.48.1.windows.1/PortableGit-2.48.1-64-bit.7z.exe"

if os.name == 'nt':  # Windows
    PYTHON_CMD = "python"  # On Windows, just use 'python'
else:  # Unix-like systems (Linux, macOS)
    # Check if 'python3' is available, otherwise fallback to 'python'
    PYTHON_CMD = "python3" if shutil.which("python3") else "python"

# Function to check if Git is installed
def check_git_installed():
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

# Prompt user for update
user_choice = input("Do you wish to check for Godfinger updates? (Y/N): ").strip().lower()
if user_choice != 'y':
    exit(0)  # Exit if the user does not want to update

def fetch_deploy():
    print(f"[DEPLOY] Checking for deployment keys in deployments.env...")
    deployment = os.path.abspath("./deployments.py")
    try:
        subprocess.run([PYTHON_CMD, deployment], check=True)
        print("Deployments script executed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error fetching deployments.py: {e}")

# Function to clone the repository if it doesn't exist
def clone_repo_if_needed():
    if os.path.isdir(os.path.join(REPO_PATH, ".git")):
        print("[GITHUB] Repo exists.")
        return
    print("[GITHUB] Cloning repository...")
    subprocess.run([GIT_EXECUTABLE, "clone", "--branch", BRANCH_NAME, REPO_URL, REPO_PATH], check=True)

# Sync repository (force update to latest commit)
def sync_repo():
    print("[GITHUB] Fetching latest changes...")
    try:
        subprocess.run([GIT_EXECUTABLE, "fetch", "--all"], check=True)
        subprocess.run([GIT_EXECUTABLE, "reset", "--hard", f"origin/{BRANCH_NAME}"], check=True)
        subprocess.run([GIT_EXECUTABLE, "pull", "origin", BRANCH_NAME], check=True)
        print("[GITHUB] Repository is now up to date.")
		
        # Get the latest commit hash
        commit_hash = subprocess.run(
            [GIT_EXECUTABLE, "rev-parse", "HEAD"], check=True, stdout=subprocess.PIPE, text=True
        ).stdout.strip()

        # Write commit hash to commit.cfg
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
    if check_git_installed():
        clone_repo_if_needed()
        sync_repo()
        fetch_deploy()
    else:
        print("[INFO] Using 7-Zip Portable to extract Git...")
        extract_7z()
        git_archive_path = download_git()
        if git_archive_path:
            extract_git(git_archive_path)

        clone_repo_if_needed()
        sync_repo()
        fetch_deploy()
        remove_temp_files()

    input("Press Enter to exit...");
    exit(0);