import os
import time
import threading
import zipfile
import requests
import subprocess
import platform
import shutil
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Define Git executable path inside virtual environment
GIT_EXECUTABLE = os.path.abspath(os.path.join("..", "venv", "GIT", "bin", "git.exe"))
os.environ["GIT_PYTHON_GIT_EXECUTABLE"] = GIT_EXECUTABLE
os.environ["PATH"] = os.path.dirname(GIT_EXECUTABLE) + ";" + os.environ["PATH"]

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
            install_choice = input("Do you wish to install Git Portable in your virtual environment? (Y/N): ").strip().lower()
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

def erase_git_credentials():
    if not os.path.exists(GIT_EXECUTABLE):
        print("[ERROR] Git not found in specified VENV PATH.")
        return
    try:
        subprocess.run([GIT_EXECUTABLE, "credential-manager-core", "erase"], check=True)
        print("[INFO] Git credentials have been erased.")
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Failed to erase Git credentials: {e}")

# Extract 7z Portable
def extract_7z():
    print(f"[EXTRACT] Extracting {SEVEN_ZIP_ARCHIVE}...")
    os.makedirs(EXTRACT_DIR, exist_ok=True)
    with zipfile.ZipFile(SEVEN_ZIP_ARCHIVE, 'r') as zip_ref:
        zip_ref.extractall(EXTRACT_DIR)
    print("[EXTRACT] Extraction complete.")

# Function to clone the repository if it doesn't exist
def clone_repo_if_needed():
    import git
    if os.path.isdir(os.path.join(REPO_PATH, ".git")):
        print("[GITHUB] Repo exists. Pulling latest changes...")
        repo = git.Repo(REPO_PATH)
        repo.remotes.origin.pull()
        return repo
    else:
        print("[GITHUB] Cloning repository...")
        return git.Repo.clone_from(REPO_URL, REPO_PATH)

# Sync repository
def sync_repo():
    import git
    origin = repo.remotes.origin
    print("[GITHUB] Fetching latest changes...")
    origin.fetch()
    
    try:
        current_commit = repo.head.commit.hexsha
    except ValueError:
        current_commit = None

    print(f"[GITHUB] Checking out branch {BRANCH_NAME}...")
    try:
        repo.git.checkout(BRANCH_NAME, force=True)
    except git.exc.GitCommandError as e:
        print(f"[ERROR] Failed to checkout branch {BRANCH_NAME}: {e}")
        return

    print("[GITHUB] Pulling latest changes...")
    origin.pull(BRANCH_NAME)

    new_commit = repo.head.commit.hexsha if repo.head.commit else None

    if current_commit and new_commit and current_commit == new_commit:
        print("[GITHUB] No changes detected.")
        return

    print("[GITHUB] Repository is up to date.")

# Function to delete temporary files
def remove_temp_files():
    if os.path.exists(EXTRACT_DIR):
        shutil.rmtree(EXTRACT_DIR, ignore_errors=True)
        print("[CLEANUP] Temporary files removed.")

# Watchdog event handler for file changes
class RepoEventHandler(FileSystemEventHandler):
    def on_any_event(self, event):
        if event.event_type in ["created", "modified", "moved"]:
            print(f"[UPDATE] Detected change: {event.src_path}")
            sync_repo()

# Start file watcher
def start_watcher():
    event_handler = RepoEventHandler()
    observer = Observer()
    observer.schedule(event_handler, REPO_PATH, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

# Main script execution
if __name__ == "__main__":
    if check_git_installed():
        import git
        repo = clone_repo_if_needed()
        sync_repo()
    else:
        print("[INFO] Using 7-Zip to extract Git...")
        extract_7z()
        git_archive_path = download_git()
        if git_archive_path:
            extract_git(git_archive_path)

        erase_git_credentials()
        repo = git.Repo.clone_from(REPO_URL, REPO_PATH)
        sync_repo()
        remove_temp_files()

    # Start file watcher
    start_watcher()