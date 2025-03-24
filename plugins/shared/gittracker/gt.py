import subprocess
import json
import os
import time
import shutil
import requests

CONFIG_FILE = "gtConfig.json"
PLACEHOLDER = "placeholder"
PLACEHOLDER_REPO = "placeholder/placeholder"
PLACEHOLDER_BRANCH = "placeholder"
GITHUB_API_URL = "https://api.github.com/repos/{}/commits?sha={}"

# Check if the system is Windows
if os.name == 'nt':  # Windows
    GIT_PATH = shutil.which("git")

    if GIT_PATH is None:
        # If Git is not found, check a fallback directory
        GIT_PATH = os.path.abspath(os.path.join("..", "..", "..", "venv", "GIT", "bin"))
        GIT_EXECUTABLE = os.path.abspath(os.path.join(GIT_PATH, "git.exe"))
    else:
        GIT_EXECUTABLE = os.path.abspath(GIT_PATH)

    PYTHON_CMD = "python"  # On Windows, just use 'python'

    # Set the environment variables for Windows if Git was found
    if GIT_EXECUTABLE:
        os.environ["GIT_PYTHON_GIT_EXECUTABLE"] = GIT_EXECUTABLE
        print(f"Git executable set to: {GIT_EXECUTABLE}")
    else:
        print("Git executable could not be set. Ensure Git is installed.")

else:  # Non-Windows (Linux, macOS)
    # Get the default Git executable path
    GIT_EXECUTABLE = shutil.which("git")
    PYTHON_CMD = "python3" if shutil.which("python3") else "python"

    if GIT_EXECUTABLE:
        os.environ["GIT_PYTHON_GIT_EXECUTABLE"] = GIT_EXECUTABLE
        print(f"Git executable set to default path: {GIT_EXECUTABLE}")
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
        exit(0)

def create_config_placeholder():
    """Creates gtConfig.json with placeholder repositories if it doesn't exist."""
    if not os.path.exists(CONFIG_FILE):
        default_config = {
            "repositories": [
                {
                    "repository": PLACEHOLDER_REPO,
                    "branch": PLACEHOLDER_BRANCH
                },
                {
                    "repository": PLACEHOLDER_REPO,
                    "branch": PLACEHOLDER_BRANCH
                }
            ],
            "refresh_interval": 60  # Check every 60 seconds
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(default_config, f, indent=2)
        print(f"Created {CONFIG_FILE} with placeholder repositories.")

def load_config():
    """Loads repository URLs, branches, and refresh interval from JSON config file."""
    if not os.path.exists(CONFIG_FILE):
        print(f"Error: Config file '{CONFIG_FILE}' not found.")
        return None, None
    
    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)
    
    repositories = config.get("repositories", [])
    refresh_interval = config.get("refresh_interval", 60)

    # Check for placeholders
    for repo in repositories:
        if repo["repository"] == PLACEHOLDER or repo["branch"] == PLACEHOLDER:
            print("\nPlaceholders detected in gtConfig.json. Please update the file.")
            input("Press Enter to exit...")
            exit(1)

    return repositories, refresh_interval

def get_latest_commit_info(repo_url: str, branch: str):
    """Fetches the latest commit hash and message from the GitHub API."""
    try:
        # Ensure that the repository URL is in the correct format "owner/repo"
        repo_name = repo_url.replace("https://github.com/", "").replace("http://github.com/", "")
        
        # Format the API URL to request the latest commit for the specific branch
        api_url = GITHUB_API_URL.format(repo_name, branch)
        
        print(f"Requesting commit info from GitHub API for {repo_name}, branch '{branch}'...")
        
        response = requests.get(api_url)
        
        if response.status_code == 200:
            commit_data = response.json()[0]  # Get the most recent commit
            commit_hash = commit_data["sha"][:7]  # Truncate the hash to 7 characters
            commit_message = commit_data["commit"]["message"]
            return commit_hash, commit_message
        else:
            print(f"Error: Failed to fetch commit info from GitHub API. Status code {response.status_code}")
            return None, None
    except requests.RequestException as e:
        print(f"Error: Could not retrieve commit info for {repo_url} on branch '{branch}'. {str(e)}")
        return None, None

def monitor_commits():
    """Continuously checks for new commits at regular intervals."""
    repositories, refresh_interval = load_config()
    
    if not repositories:
        print("No repositories found in config.json.")
        return
    
    last_commit_info = {}  # Store the last commit info for each repository/branch
    
    try:
        while True:
            for i, repo in enumerate(repositories, 1):
                repo_url = repo["repository"]
                branch_name = repo["branch"]

                commit_hash, commit_message = get_latest_commit_info(repo_url, branch_name)
                
                if commit_hash and commit_message:
                    repo_key = f"{repo_url}_{branch_name}"

                    if repo_key in last_commit_info:
                        last_hash, last_message = last_commit_info[repo_key]

                        # Check if the commit hash and message are the same
                        if commit_hash == last_hash and commit_message == last_message:
                            print(f"Latest HEAD already found for {repo_url} {branch_name}. Sleeping...\n")
                            continue  # Skip to the next iteration

                    # Store new commit info for this repository/branch pair
                    last_commit_info[repo_key] = (commit_hash, commit_message)

                    # Store commit info separately for each repository using _1, _2, etc.
                    print(f"\nNew commit detected for repository {i} ('{branch_name}') in '{repo_url}':")
                    print(f"Hash: {commit_hash}")
                    print(f"Message: {commit_message}")

                    # Here you can send the commit information to svsay through rcon or handle it as needed

            print("Sleeping...")
            time.sleep(refresh_interval)

    except KeyboardInterrupt:
        print("\nMonitoring stopped by user.")

if __name__ == "__main__":
    create_config_placeholder()  # Ensure gtConfig.json exists with placeholder values
    check_git_installed()
    monitor_commits()
