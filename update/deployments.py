import os
import subprocess
import shutil
from dotenv import load_dotenv
import stat
import sys

# Define file paths
ENV_FILE = "deployments.env"
DEPLOY_DIR = "./deploy"
KEY_DIR = "./key"

# Determine GIT_EXECUTABLE path based on OS
if os.name == 'nt':  # Windows
    GIT_PATH = shutil.which("git")

    if GIT_PATH is None:
        # If Git is not found, check a fallback directory
        GIT_PATH = os.path.abspath(os.path.join("..", "venv", "GIT", "bin"))
        GIT_EXECUTABLE = os.path.abspath(os.path.join(GIT_PATH, "git.exe"))
    else:
        GIT_EXECUTABLE = os.path.abspath(GIT_PATH)

    PYTHON_CMD = sys.executable

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

# Create default .env if it doesn't exist
if not os.path.exists(ENV_FILE):
    with open(ENV_FILE, "w") as f:
        f.writelines([ 
            "placeholder=./key/key\n",
            "placeholder=./key/key\n",
            "placeholder=./key/key\n",
            "placeholder=./key/key\n",
        ])
    print(f"Created {ENV_FILE} with placeholder values.")

# Load .env file
load_dotenv(ENV_FILE)

# Ensure deploy directory exists
os.makedirs(DEPLOY_DIR, exist_ok=True)
os.makedirs(KEY_DIR, exist_ok=True)

# Read deployments from .env
deployments = {}
with open(ENV_FILE, "r") as f:
    for line in f:
        line = line.strip()
        if "=" in line and line != "placeholder=":
            repo_branch, deploy_key = line.split("=", 1)
            if deploy_key and repo_branch != "placeholder":
                deployments[repo_branch] = deploy_key

# If no valid deployments found, print message and exit
if not deployments:
    print("No deployments to manage. Press enter to continue...")
    input()
    exit(0)

# Process deployments
latest_commits = {}
for repo_branch, deploy_key in deployments.items():
    # Parse the repo_branch to get account, repo, and branch
    account_repo, branch = repo_branch.rsplit("/", 1)
    account, repo = account_repo.split("/", 1)  # Split into account and repo name
    
    repo_dir = os.path.join(DEPLOY_DIR, repo_branch.replace("/", "_"))  # Avoiding slashes in folder names

    # Ensure the repo folder exists
    if not os.path.exists(repo_dir):
        os.makedirs(repo_dir)

    # Set up SSH command with debugging output (absolute path to the key)
    absolute_key_path = os.path.abspath(deploy_key)  # Get absolute path to the key
    quoted_key_path = f"\"{absolute_key_path}\""  # Wrap path in quotes for spaces handling
    print(f"Using SSH key: {quoted_key_path}")  # Debugging the key path

    # Ensure the private key has the correct permissions (only readable by the owner)
    try:
        key_stat = os.stat(absolute_key_path)
        if key_stat.st_mode & stat.S_IRWXO:  # Check for world-readable permissions
            print(f"Fixing permissions for {absolute_key_path}")
            os.chmod(absolute_key_path, 0o600)  # Set to read/write only for the user
    except Exception as e:
        print(f"Error checking or setting permissions for {absolute_key_path}: {e}")

    # Ensure SSH command is correctly quoted
    ssh_command = f"ssh -i {quoted_key_path} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
    git_env = {**os.environ, "GIT_SSH_COMMAND": ssh_command}

    # Test SSH connection manually
    try:
        repo_url = f"git@github.com:{account}/{repo}.git"  # Use full repository URL
        subprocess.run([GIT_EXECUTABLE, "ls-remote", repo_url, "--exit-code"], check=True, env=git_env)
        print(f"SSH authentication with {repo_url} successful.")
    except subprocess.CalledProcessError as e:
        print(f"Error with SSH authentication to GitHub: {e}")
        continue

    # If repo does not exist, clone it
    if not os.path.exists(os.path.join(repo_dir, ".git")):
        # Build the GitHub URL for cloning with /tree/{branch}
        try:
            subprocess.run([GIT_EXECUTABLE, "clone", "-b", branch, repo_url, repo_dir], check=True, env=git_env)
        except subprocess.CalledProcessError as e:
            print(f"Error cloning {repo_branch}: {e}")
            continue
    else:
        # If the repo already exists, fetch and reset with the specified key
        try:
            # Explicitly set the SSH key for fetch and reset
            print(f"Running fetch with SSH key for {repo_branch}")
            subprocess.run([GIT_EXECUTABLE, "fetch", "--all"], cwd=repo_dir, check=True, env=git_env)
            subprocess.run([GIT_EXECUTABLE, "reset", "--hard", f"origin/{branch}"], cwd=repo_dir, check=True, env=git_env)
        except subprocess.CalledProcessError as e:
            print(f"Error updating {repo_branch}: {e}")
            continue

    # Ask for commit hash (optional)
    commit_hash = input(f"\nEnter specific commit hash for {repo_branch} (or press Enter to deploy latest HEAD): ").strip()
    
    # If the user doesn't provide a commit hash, get the latest HEAD
    if not commit_hash:
        try:
            result = subprocess.run([GIT_EXECUTABLE, "rev-parse", "HEAD"], cwd=repo_dir, capture_output=True, text=True, check=True)
            commit_hash = result.stdout.strip()
            print(f"Using latest HEAD: {commit_hash}")
        except subprocess.CalledProcessError as e:
            print(f"Error getting latest commit hash for {repo_branch}: {e}")
            continue

    # Checkout specific commit if provided
    try:
        # Disable detached HEAD advice
        subprocess.run([GIT_EXECUTABLE, "config", "--local", "advice.detachedHead", "false"], cwd=repo_dir, check=True)
        subprocess.run([GIT_EXECUTABLE, "checkout", commit_hash], cwd=repo_dir, check=True, env=git_env)
        print(f"Checked out commit {commit_hash} for {repo_branch}")
        latest_commits[repo_branch] = commit_hash
    except subprocess.CalledProcessError as e:
        print(f"Error checking out commit {commit_hash} for {repo_branch}: {e}")
        continue

    print(f"Deployed {repo_branch} -> {repo_dir}")

print("Deployment process completed.")
input("Press Enter to exit...")
