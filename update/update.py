import os
import time
import git
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Set repository paths
REPO_PATH = "https://github.com/MBII-Galactic-Conquest/godfinger"
SYNC_PATH = "../"  # Optional: Where to copy updated files
BRANCH_NAME = "dev"  # Change this to the branch you want to sync

# Initialize repo
repo = git.Repo(REPO_PATH)
stop_flag = False  # Flag to signal stopping the script

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

    # Checkout and pull from the specified branch
    print(f"[INFO] Checking out branch {BRANCH_NAME}...")
    repo.git.checkout(BRANCH_NAME)

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
        while not stop_flag:
            time.sleep(10)
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()

# Function to wait for user input to stop the script
def wait_for_exit():
    global stop_flag
    input("\nPress Enter to exit...\n")
    stop_flag = True

# Main loop to check for new files periodically
if __name__ == "__main__":
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