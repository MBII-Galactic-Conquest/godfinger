import os
import subprocess
import update
from dotenv import load_dotenv

# Define file paths
ENV_FILE = "deployments.env"
CFG_FILE = "deployments.cfg"
DEPLOY_DIR = "./deploy"

# Check if the system is Windows
if os.name == 'nt':  # Windows
    GIT_PATH = os.path.abspath(os.path.join("..", "venv", "GIT", "bin"))
    GIT_EXECUTABLE = os.path.abspath(os.path.join("..", "venv", "GIT", "bin", "git.exe"))
    PYTHON_CMD = "python"  # On Windows, just use 'python'
    
    # Set the environment variables for Windows
    os.environ["GIT_PYTHON_GIT_EXECUTABLE"] = GIT_EXECUTABLE
    os.environ["PATH"] = os.path.dirname(GIT_PATH) + ";" + os.environ["PATH"]
    print(f"Git executable set to: {GIT_EXECUTABLE}")
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
            "placeholder=\n",
            "placeholder=\n",
            "placeholder=\n",
            "placeholder=\n"
        ])
    print(f"Created {ENV_FILE} with placeholder values.")

# Load .env file
load_dotenv(ENV_FILE)

# Ensure deploy directory exists
os.makedirs(DEPLOY_DIR, exist_ok=True)

# Read deployments from .env
deployments = {}
with open(ENV_FILE, "r") as f:
    for line in f:
        line = line.strip()
        if "=" in line:
            repo_branch, deploy_key = line.split("=", 1)
            if deploy_key and repo_branch != "placeholder":
                deployments[repo_branch] = deploy_key

# Process deployments
latest_commits = {}
for repo_branch, deploy_key in deployments.items():
    repo, branch = repo_branch.split("/", 1)
    repo_dir = os.path.join(DEPLOY_DIR, repo_branch.replace("/", "_"))  # Avoiding slashes in folder names

    # Ensure the repo folder exists
    if not os.path.exists(repo_dir):
        os.makedirs(repo_dir)

    # Set up SSH command
    ssh_command = f"ssh -i {deploy_key} -o StrictHostKeyChecking=no"
    git_env = {**os.environ, "GIT_SSH_COMMAND": ssh_command}

    try:
        # If repo exists, pull updates; otherwise, clone
        if os.path.exists(os.path.join(repo_dir, ".git")):
            subprocess.run(["git", "fetch", "--all"], cwd=repo_dir, check=True, env=git_env)
            subprocess.run(["git", "reset", "--hard", f"origin/{branch}"], cwd=repo_dir, check=True, env=git_env)
        else:
            repo_url = f"git@github.com:{repo}.git"
            subprocess.run(["git", "clone", "-b", branch, repo_url, repo_dir], check=True, env=git_env)

        # Get latest commit hash
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_dir, capture_output=True, text=True, check=True)
        latest_commits[repo_branch] = result.stdout.strip()

        print(f"Updated {repo_branch} -> {repo_dir}")

    except subprocess.CalledProcessError as e:
        print(f"Error processing {repo_branch}: {e}")

# Update deployments.cfg with latest commit hashes
with open(CFG_FILE, "w") as f:
    for repo_branch, commit_hash in latest_commits.items():
        f.write(f"{repo_branch}={commit_hash}\n")

print("Deployment process completed.")
input("Press Enter to exit...");
exit(0);
