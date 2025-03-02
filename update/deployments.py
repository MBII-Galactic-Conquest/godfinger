import os
import subprocess
import shutil
from dotenv import load_dotenv

# Define file paths
ENV_FILE = "deployments.env"
CFG_FILE = "deployments.cfg"
DEPLOY_DIR = "./deploy"
KEY_DIR = "./key"

if os.name == 'nt':  # Windows
    GIT_PATH = shutil.which("git")

    if GIT_PATH is None:
        # If Git is not found, check a fallback directory
        GIT_PATH = os.path.abspath(os.path.join("..", "venv", "GIT", "bin"))
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

    # Set up SSH command
    ssh_command = f"ssh -i {deploy_key} -o StrictHostKeyChecking=no"
    git_env = {**os.environ, "GIT_SSH_COMMAND": ssh_command}

    try:
        # Build the GitHub URL for cloning with /tree/{branch}
        repo_url = f"git@github.com:{account}/{repo}.git"
        if os.path.exists(os.path.join(repo_dir, ".git")):
            subprocess.run([GIT_EXECUTABLE, "fetch", "--all"], cwd=repo_dir, check=True, env=git_env)
            subprocess.run([GIT_EXECUTABLE, "reset", "--hard", f"origin/{branch}"], cwd=repo_dir, check=True, env=git_env)
        else:
            subprocess.run([GIT_EXECUTABLE, "clone", "-b", branch, repo_url, repo_dir], check=True, env=git_env)

        # Get latest commit hash
        result = subprocess.run([GIT_EXECUTABLE, "rev-parse", "HEAD"], cwd=repo_dir, capture_output=True, text=True, check=True)
        latest_commits[repo_branch] = result.stdout.strip()

        print(f"Updated {repo_branch} -> {repo_dir}")

    except subprocess.CalledProcessError as e:
        print(f"Error processing {repo_branch}: {e}")

# Update deployments.cfg with latest commit hashes
with open(CFG_FILE, "w") as f:
    for repo_branch, commit_hash in latest_commits.items():
        f.write(f"{repo_branch}={commit_hash}\n")

print("Deployment process completed.")
input("Press Enter to exit...")
exit(0)
