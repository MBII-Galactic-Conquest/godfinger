import os
import time
import git
import threading
import zipfile
import requests
import subprocess
import platform
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Set repository paths and remote URL
REPO_URL = "https://github.com/MBII-Galactic-Conquest/godfinger"  # Replace with the actual repo URL
REPO_PATH = "../"  # Local path to store the repository
BRANCH_NAME = "dev"  # Branch you want to sync
CFG_FILE_PATH = "commit.cfg"  # Path to the .cfg file

# Directory for extracting 7z files (relative to root working directory)
EXTRACT_DIR = "../temp"  # This is the folder where the 7z archive will be extracted
SEVEN_ZIP_EXECUTABLE = os.path.join(EXTRACT_DIR, '7-ZipPortable', 'App', '7-Zip', '7z.exe')  # Path to 7z.exe
SEVEN_ZIP_ARCHIVE = "7z_portable.zip"  # The bundled portable 7-Zip archive
SEVEN_ZIP_URL = "https://github.com/MBII-Galactic-Conquest/godfinger/raw/portablegit/lib/other/win/7z_portable.zip"
GIT_ARCHIVE = "PortableGit-2.48.1-64-bit.7z.exe"
GIT_URL = "https://github.com/git-for-windows/git/releases/download/v2.48.1.windows.1/PortableGit-2.48.1-64-bit.7z.exe"

# Function to check if Git is installed
def check_git_installed():
    try:
        subprocess.run(["git", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("[INFO] Git is installed.")
        return True
    except subprocess.CalledProcessError:
        if platform.system() == "Linux" or platform.system() == "Darwin":  # Unix-based systems
            print("[ERROR] Git is not installed.")
            print("You will have to install Git manually on UNIX. Visit: https://git-scm.com/downloads")
            input("Press Enter to exit...")  # Prompt user to press Enter to exit
            exit(0)
        else:
            print("[ERROR] Git is not installed.")
            install_choice = input("Do you wish to install Git manually? (Y/N): ").strip().lower()
            if install_choice == 'y':
                return False
            else:
                exit(0)

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

# Function to extract the PortableGit archive using 7-Zip
def extract_git(git_archive_path):
    print(f"[EXTRACT] Extracting {GIT_ARCHIVE} to ../venv/GIT...")
    extract_dir = "../venv/GIT"
    os.makedirs(extract_dir, exist_ok=True)  # Create the GIT extraction directory if it doesn't exist
    
    try:
        subprocess.run([SEVEN_ZIP_EXECUTABLE, "x", git_archive_path, f"-o{extract_dir}"], check=True)
        print(f"[EXTRACT] Extraction complete to {extract_dir}")
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Failed to extract {GIT_ARCHIVE}: {e}")
        return False
    return True

# Prompt user for update
user_choice = input("Do you wish to check for Godfinger updates? (Y/N): ").strip().lower()
if user_choice != 'y':
    exit(0)  # Exit if the user does not want to update

# Function to download the 7z_portable.zip file
def download_7z():
    print("[DOWNLOAD] Downloading 7z_portable.zip...")
    response = requests.get(SEVEN_ZIP_URL)
    if response.status_code == 200:
        with open(SEVEN_ZIP_ARCHIVE, 'wb') as f:
            f.write(response.content)
        print(f"[DOWNLOAD] Successfully downloaded {SEVEN_ZIP_ARCHIVE}")
    else:
        print(f"[ERROR] Failed to download {SEVEN_ZIP_ARCHIVE} from {SEVEN_ZIP_URL}")

# Function to extract 7z_portable.zip into the EXTRACT_DIR folder
def extract_7z():
    print(f"[EXTRACT] Extracting {SEVEN_ZIP_ARCHIVE} to {EXTRACT_DIR}...")
    os.makedirs(EXTRACT_DIR, exist_ok=True)  # Create the extraction directory if it doesn't exist
    with zipfile.ZipFile(SEVEN_ZIP_ARCHIVE, 'r') as zip_ref:
        zip_ref.extractall(EXTRACT_DIR)
    print(f"[EXTRACT] Extraction complete to {EXTRACT_DIR}")

# Initialize repo (clone if not already present)
if not os.path.exists(REPO_PATH):
    print(f"[GITHUB] Cloning repository from {REPO_URL} to {REPO_PATH}...")
    repo = git.Repo.clone_from(REPO_URL, REPO_PATH)
else:
    repo = git.Repo(REPO_PATH)

stop_flag = threading.Event()  # Flag to signal stopping the script

# Function to sync the repo with a specific branch
def sync_repo():
    global repo
    origin = repo.remotes.origin
    upstream = repo.remotes.upstream if "upstream" in repo.remotes else None

    print(f"[GITHUB] Fetching latest changes from branch {BRANCH_NAME}...")
    origin.fetch()
    if upstream:
        upstream.fetch()

    # Try to get the current commit hash, handle empty repo scenario
    try:
        current_commit = repo.head.commit.hexsha
    except ValueError:  # Happens if no commits exist yet
        print(f"[WARNING] No commits found in {BRANCH_NAME}. Proceeding with initial setup.")
        current_commit = None

    # Force checkout to discard any local changes and switch to the target branch
    print(f"[GITHUB] Checking out branch {BRANCH_NAME}...")
    try:
        repo.git.checkout(BRANCH_NAME, force=True)  # Force the checkout
    except git.exc.GitCommandError as e:
        print(f"[ERROR] Failed to checkout branch {BRANCH_NAME}: {e}")
        return

    print(f"[GITHUB] Pulling latest changes from {BRANCH_NAME} on origin...")
    origin.pull(BRANCH_NAME)

    # Get the new commit hash after pulling
    try:
        new_commit = repo.head.commit.hexsha
    except ValueError:
        new_commit = None

    # Check if there were any changes
    if current_commit and new_commit and current_commit == new_commit:
        print(f"[GITHUB] No changes detected on {BRANCH_NAME}, aborting update process.")
        return

    # Merge upstream changes from the same branch (if applicable)
    if upstream:
        print(f"[GITHUB] Merging upstream/{BRANCH_NAME} into local {BRANCH_NAME}...")
        repo.git.merge(f"upstream/{BRANCH_NAME}")

    print(f"[GITHUB] Repository is up to date with {BRANCH_NAME}.")

# Function to write commit hash to .cfg file
def write_commit_to_cfg(commit_hash):
    try:
        with open(CFG_FILE_PATH, "w") as cfg_file:
            cfg_file.write(f"commit_hash={commit_hash}\n")
        print(f"[GITHUB] Written commit hash {commit_hash} to {CFG_FILE_PATH}.")
    except Exception as e:
        print(f"[ERROR] Failed to write to {CFG_FILE_PATH}: {e}")

# Function to check for new files
def get_new_files():
    repo.git.fetch()
    commits = list(repo.iter_commits(BRANCH_NAME, max_count=2))

    if len(commits) < 2:
        return []

    # Get the latest and previous commit
    latest_commit = commits[0]
    prev_commit = commits[1]

    # Compare trees
    diff = latest_commit.diff(prev_commit)
    new_files = [item.b_path for item in diff if item.new_file]

    return new_files

# Watchdog event handler for file changes
class RepoEventHandler(FileSystemEventHandler):
    def on_any_event(self, event):
        if event.event_type in ["created", "modified", "moved"]:
            print(f"[UPDATE] Detected change: {event.src_path}")
            sync_repo()

# Function to start the watchdog observer
def start_watcher():
    global stop_flag
    event_handler = RepoEventHandler()
    observer = Observer()
    observer.schedule(event_handler, REPO_PATH, recursive=True)
    observer.start()

    try:
        while not stop_flag.is_set():
            time.sleep(0.5)  # Adjust sleep time for quicker response to `stop_flag`
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()

# Function to wait for user input to stop the script
def wait_for_exit():
    global stop_flag
    input("\nPress Enter to continue...\n")
    stop_flag.set()

# Main loop to check for new files periodically
if __name__ == "__main__":
    # Check if Git is installed or if the user is on Windows without Git
    if check_git_installed():
        sync_repo()
    elif platform.system() == "Windows":
        print("[INFO] Windows detected, Git not found. Using 7-Zip as an alternative.")
        download_7z()
        extract_7z()

        # Download Git if not installed
        git_archive_path = download_git()
        if git_archive_path:
            extract_git(git_archive_path)

        # Proceed as if Git was installed
        repo = git.Repo.clone_from(REPO_URL, REPO_PATH)  # Cloning repository in case Git isn't present
        sync_repo()
    else:
        print("[ERROR] Git is not installed and this script cannot proceed on this platform.")

    # Get initial commit hash and write to .cfg if not present
    try:
        initial_commit = repo.head.commit.hexsha
        if os.path.exists(CFG_FILE_PATH):
            print(f"[GITHUB] Found existing {CFG_FILE_PATH}.")
        else:
            print(f"[GITHUB] No {CFG_FILE_PATH} file found. Creating a new one.")
            write_commit_to_cfg(initial_commit)
    except ValueError:
        print(f"[GITHUB] No commits found in the repository. Unable to determine initial commit.")

    new_files = get_new_files()
    if new_files:
        print(f"[GITHUB] New files detected: {new_files}")

    # Start watcher and exit listener in separate threads
    exit_thread = threading.Thread(target=wait_for_exit, daemon=True)
    exit_thread.start()

    start_watcher()

    print("[GITHUB] Exiting script.")