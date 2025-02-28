import os
import time
import git
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Set repository paths and remote URL
REPO_URL = "https://github.com/MBII-Galactic-Conquest/godfinger"  # Replace with the actual repo URL
REPO_PATH = "../"  # Local path to store the repository
SYNC_PATH = "../"  # Optional: Where to copy updated files
BRANCH_NAME = "update"  # Branch you want to sync
CFG_FILE_PATH = "commit.cfg"  # Path to the .cfg file

# Initialize repo (clone if not already present)
if not os.path.exists(REPO_PATH):
    print(f"[INFO] Cloning repository from {REPO_URL} to {REPO_PATH}...")
    git.Repo.clone_from(REPO_URL, REPO_PATH)
else:
    repo = git.Repo(REPO_PATH)

stop_flag = threading.Event()  # Flag to signal stopping the script

# Function to sync the repo with a specific branch
def sync_repo():
    global repo
    origin = repo.remotes.origin
    upstream = repo.remotes.upstream if "upstream" in repo.remotes else None

    print(f"[INFO] Fetching latest changes from branch {BRANCH_NAME}...")
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
    print(f"[INFO] Checking out branch {BRANCH_NAME}...")
    try:
        repo.git.checkout(BRANCH_NAME, force=True)  # Force the checkout
    except git.exc.GitCommandError as e:
        print(f"[ERROR] Failed to checkout branch {BRANCH_NAME}: {e}")
        return

    print(f"[INFO] Pulling latest changes from {BRANCH_NAME} on origin...")
    origin.pull(BRANCH_NAME)

    # Get the new commit hash after pulling
    try:
        new_commit = repo.head.commit.hexsha
    except ValueError:
        new_commit = None

    # Check if there were any changes
    if current_commit and new_commit and current_commit == new_commit:
        print(f"[INFO] No changes detected on {BRANCH_NAME}, aborting update process.")
        return

    # Merge upstream changes from the same branch (if applicable)
    if upstream:
        print(f"[INFO] Merging upstream/{BRANCH_NAME} into local {BRANCH_NAME}...")
        repo.git.merge(f"upstream/{BRANCH_NAME}")

    print(f"[INFO] Repository is up to date with {BRANCH_NAME}.")

    # Write the latest commit to the .cfg file
    write_commit_to_cfg(new_commit)

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

# Function to write the commit hash to the .cfg file (overwrites with latest)
def write_commit_to_cfg(commit_hash):
    # Open the .cfg file in write mode to overwrite any previous data
    with open(CFG_FILE_PATH, "w") as cfg_file:
        cfg_file.write(f"[Commit]\n")
        cfg_file.write(f"latest_commit={commit_hash}\n")
    print(f"[INFO] Latest commit hash written to {CFG_FILE_PATH}")

# Function to initialize the .cfg file if it doesn't exist
def initialize_cfg():
    # If the config file doesn't exist, write the initial commit hash
    if not os.path.exists(CFG_FILE_PATH):
        print("[INFO] .cfg file not found, initializing...")
        # Get the initial commit hash from the repo
        initial_commit = repo.head.commit.hexsha
        print(f"[INFO] Initial commit hash: {initial_commit}")
        write_commit_to_cfg(initial_commit)

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
            time.sleep(10)
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()

# Function to wait for user input to stop the script
def wait_for_exit():
    global stop_flag
    print("\nPress any key to exit...")
    input()  # This will break the loop instantly when any key is pressed
    stop_flag.set()  # Signal to stop the script

# Main loop to check for new files periodically
if __name__ == "__main__":
    initialize_cfg()  # Initialize .cfg file with the first commit hash if necessary
    sync_repo()
    new_files = get_new_files()
    if new_files:
        print(f"[INFO] New files detected: {new_files}")
        if SYNC_PATH:
            os.system(f"rsync -av --delete {REPO_PATH}/ {SYNC_PATH}/")

    # Start watcher and exit listener in separate threads
    exit_thread = threading.Thread(target=wait_for_exit, daemon=True)
    exit_thread.start()

    start_watcher()

    print("[INFO] Exiting script.")
