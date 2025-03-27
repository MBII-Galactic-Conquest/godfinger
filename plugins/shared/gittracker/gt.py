import logging;
import godfingerEvent;
import pluginExports;
import lib.shared.serverdata as serverdata
import lib.shared.colors as colors
import subprocess
import json
import sys
import os
import time
import shutil
import requests
import threading
import platform
from dotenv import load_dotenv, set_key

SERVER_DATA = None;
GODFINGER = "godfinger"
Log = logging.getLogger(__name__);

## Requires that your REPOSITORY is publicly visible ##

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "gtConfig.json");
PLACEHOLDER = "placeholder"
PLACEHOLDER_PATH = "path/to/bat/or/sh"
PLACEHOLDER_REPO = "placeholder/placeholder"
PLACEHOLDER_BRANCH = "placeholder"
GITHUB_API_URL = "https://api.github.com/repos/{}/commits?sha={}"

UPDATE_NEEDED = False
FALSE_VAR = False

if os.name == 'nt':  # Windows
    GIT_PATH = shutil.which("git")

    if GIT_PATH is None:
        GIT_PATH = os.path.abspath(os.path.join("venv", "GIT", "bin"))
        GIT_EXECUTABLE = os.path.abspath(os.path.join(GIT_PATH, "git.exe"))
    else:
        GIT_EXECUTABLE = os.path.abspath(GIT_PATH)

    PYTHON_CMD = sys.executable

    if GIT_EXECUTABLE:
        os.environ["GIT_PYTHON_GIT_EXECUTABLE"] = GIT_EXECUTABLE
        #print(f"Git executable set to: {GIT_EXECUTABLE}")
    else:
        print("Git executable could not be set. Ensure Git is installed.")

else:  # Non-Windows (Linux, macOS)
    GIT_EXECUTABLE = shutil.which("git")
    PYTHON_CMD = "python3" if shutil.which("python3") else "python"

    if GIT_EXECUTABLE:
        os.environ["GIT_PYTHON_GIT_EXECUTABLE"] = GIT_EXECUTABLE
        #print(f"Git executable set to default path: {GIT_EXECUTABLE}")
    else:
        print("Git executable not found on the system.")

class gitTrackerPlugin(object):
    def __init__(self, serverData : serverdata.ServerData) -> None:
        self._serverData : serverdata.ServerData = serverData
        self._messagePrefix = colors.ColorizeText("[GT]", "lblue") + ": "

def check_git_installed():
    global GIT_EXECUTABLE
    if shutil.which("git") or os.path.exists(GIT_EXECUTABLE):
        try:
            subprocess.run([GIT_EXECUTABLE, "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            print("[GT] Git is installed.")
            return True
        except subprocess.CalledProcessError:
            print("[GT] Git version check failed.")
            return False
    else:
        print("[ERROR] Git is not installed. Plugin cannot continue.")
        sys.exit(0)

def create_config_placeholder():
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
            "refresh_interval": 60,
            "gfBuildBranch": PLACEHOLDER_BRANCH,
            "svnPostHookFile": PLACEHOLDER_PATH,
            "isSVNBuilding": FALSE_VAR,
            "isGFBuilding": FALSE_VAR
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(default_config, f, indent=2)
        print(f"Created {CONFIG_FILE} with placeholder repositories.")

def load_config():
    if not os.path.exists(CONFIG_FILE):
        print(f"Error: Config file '{CONFIG_FILE}' not found.")
        return None

    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)

    for repo in config.get("repositories", []):
        if repo["repository"] == PLACEHOLDER or repo["branch"] == PLACEHOLDER:
            print("\nPlaceholders detected in gtConfig.json. Please update the file.")
            sys.exit(0)

    return {
        "repositories": config.get("repositories", []),
        "refresh_interval": config.get("refresh_interval"),
        "gfBuildBranch": config.get("gfBuildBranch"),
        "svnPostHookFile": config.get("svnPostHookFile"),
        "isSVNBuilding": config.get("isSVNBuilding"),
        "isGFBuilding": config.get("isGFBuilding"),
    }

def get_env_file_name(repo_url, branch_name):
    repo_name = repo_url.split('/')[-1]
    return f"{repo_name}_{branch_name}.env"

def load_or_create_env(repo_url, branch_name):
    env_dir = os.path.join(os.path.dirname(__file__), "env")
    if not os.path.exists(env_dir):
        os.makedirs(env_dir)

    # Ensure each repository gets its own .env file
    env_file = get_env_file_name(repo_url, branch_name)
    env_file_path = os.path.join(env_dir, env_file)

    if not os.path.exists(env_file_path):
        #Log.info(f"Creating .env file: {env_file_path}")
        # Create new .env file with placeholders
        set_key(env_file_path, "last_hash", "")
        set_key(env_file_path, "last_message", "")
        last_hash, last_message = "", ""  # Placeholder values if new
    else:
        #Log.info(f".env file exists: {env_file_path}")
        pass;
    
    # Load existing .env data
    load_dotenv(env_file_path)
    last_hash = os.getenv("last_hash")
    last_message = os.getenv("last_message")
    
    return last_hash, last_message, env_file_path

def update_env_file_if_needed(repo_url, branch_name, commit_hash, commit_message, isGFBuilding, gfBuildBranch):
    global PluginInstance
    global UPDATE_NEEDED

    # First, reset last_hash and last_message
    last_hash, last_message, env_file_path = load_or_create_env(repo_url, branch_name)
    repo_name = repo_url.replace("MBII-Galactic-Conquest/", "").replace("MBII-Galactic-Conquest/", "")
    
    # Trim whitespace from the values
    commit_hash = commit_hash.strip()
    commit_message = commit_message.strip()[:60]
    last_hash = last_hash.strip()[:60] if last_hash else ""
    last_message = last_message.strip()[:60] if last_message else ""

    if "'" or "\n" in commit_message:
        commit_message = commit_message.replace("'", "/")
        commit_message = commit_message.replace("\n", "")

    #Log.info(f"Comparing commit info for {repo_url} ({branch_name}):")
    #Log.info(f"Last commit hash: {last_hash}")
    #Log.info(f"Last commit message: {last_message}")
    #Log.info(f"New commit hash: {commit_hash}")
    #Log.info(f"New commit message: {commit_message}")

    if last_hash == commit_hash or last_message == commit_message:
        pass;

    # Check if the commit hash or message has changed for this specific repository
    if last_hash != commit_hash or last_message != commit_message:
        #Log.info(f"Updating .env file for {repo_url} ({branch_name}) with new commit (Hash: {commit_hash}, Message: {commit_message})")
        # Only update if hash or message has changed
        set_key(env_file_path, "last_hash", commit_hash)
        set_key(env_file_path, "last_message", commit_message)
        full_message = f"^5{commit_hash} ^7- {repo_name}/{branch_name} - ^5{commit_message}"
        if last_hash == commit_hash or last_message == commit_message:
            pass;
        if len(full_message) > 131:
            max_commit_message_length = 131 - len(f"^5{commit_hash} ^7- {repo_name}/{branch_name} - ^5") - 3
            commit_message = commit_message[:max_commit_message_length] + "..."
            full_message = f"^5{commit_hash} ^7- {repo_name}/{branch_name} - ^5{commit_message}"
        PluginInstance._serverData.interface.SvSay(PluginInstance._messagePrefix + full_message)
        if isGFBuilding == True and UPDATE_NEEDED == False and GODFINGER in repo_name and gfBuildBranch in branch_name:
            PluginInstance._serverData.interface.SvSay(PluginInstance._messagePrefix + "^1[!] ^7Godfinger change detected, applying when all players leave the server...")
            UPDATE_NEEDED = True
            return UPDATE_NEEDED
    else:
        #Log.info(f"No changes for {repo_url} ({branch_name}). Commit (Hash: {commit_hash}, Message: {commit_message}) is the same as the last one.")
        pass;

    # Reset the values after processing to ensure no state leakage for the next repository
    last_hash = None
    last_message = None

    # Optionally, clear out environment variables to prevent interference between repository checks
    os.environ.pop("last_hash")
    os.environ.pop("last_message")

def get_latest_commit_info(repo_url: str, branch: str):
    try:
        repo_name = repo_url.replace("https://github.com/", "").replace("http://github.com/", "")
        api_url = GITHUB_API_URL.format(repo_name, branch)
        
        #Log.info(f"Requesting commit info from GitHub API for {repo_name}, branch '{branch}'...")

        response = requests.get(api_url)

        if response.status_code == 403:
            Log.info(response.headers.get('X-RateLimit-Remaining'))

        if response.status_code == 200:
            commit_data = response.json()[0]
            commit_hash = commit_data["sha"][:7]
            commit_message = commit_data["commit"]["message"]
            return commit_hash, commit_message
        else:
            #Log.info(f"Error: Failed to fetch commit info from GitHub API. Status code {response.status_code}")
            return None, None
    except requests.RequestException as e:
        #Log.info(f"Error: Could not retrieve commit info for {repo_url} on branch '{branch}'. {str(e)}")
        return None, None

def monitor_commits():
    config = load_config()
    if config:
        repositories = config["repositories"]
        refresh_interval = config["refresh_interval"]
        gfBuildBranch = config["gfBuildBranch"]
        isGFBuilding = config["isGFBuilding"]
    
    if not repositories:
        print("No repositories found in gtConfig.json.")
        return
    
    try:
        while True:
            #Log.info("Starting commit check loop...")
            for i, repo in enumerate(repositories, 1):
                #Log.info(f"Checking repository {i}: {repo['repository']} on branch {repo['branch']}")
                repo_url = repo["repository"]
                branch_name = repo["branch"]

                commit_hash, commit_message = get_latest_commit_info(repo_url, branch_name)

                if commit_hash and commit_message:
                    #Log.info(f"\nNew commit detected for repository {i} ('{branch_name}') in '{repo_url}':")
                    #Log.info(f"Hash: {commit_hash}")
                    #Log.info(f"Message: {commit_message}")

                    update_env_file_if_needed(repo_url, branch_name, commit_hash, commit_message, isGFBuilding, gfBuildBranch)

            time.sleep(refresh_interval)

    except KeyboardInterrupt:
        print("\nMonitoring stopped by user.")

def start_monitoring():
    monitoring_thread = threading.Thread(target=monitor_commits)
    monitoring_thread.daemon = True
    monitoring_thread.start()

def CheckForSVNUpdate(isSVNBuilding, svnPostHookFile):
    global UPDATE_NEEDED

# Used to check for SVN updates as well, using post hooks #
# Excellent for json configstores, private codebases, and other implements #

    script_path = os.path.abspath(os.path.join(os.getcwd(), svnPostHookFile))
    
    if isSVNBuilding and UPDATE_NEEDED == True:
        if not os.path.exists(script_path):
            Log.error(f"SVN Post Hook file not found: {script_path}")
            return
        try:
            if script_path.endswith('.bat') and os.name == 'nt':  # Windows
                subprocess.run(script_path, shell=True, check=True)
            elif script_path.endswith('.sh') and os.name != 'nt':  # Linux/macOS
                subprocess.run(["bash", script_path], check=True)
            else:
                Log.error("Unsupported script type or OS")
            Log.info(f"Successfully executed SVN Update: {script_path}")
        except subprocess.CalledProcessError as e:
            Log.error(f"Error executing SVN Update: {e}")
    else:
        pass;

def run_script(script_path, simulated_inputs):
    global PYTHON_CMD
    CWD = os.getcwd()

    if not os.path.exists(script_path):
        Log.error(f"Script not found: {script_path}")
        #print(f"Debug: Script not found: {script_path}")
        return

    input_string = "\n".join(simulated_inputs) + "\n"
    #print(f"Debug: Running {script_path} with input: {input_string}")

    try:
        result = subprocess.run(
            [PYTHON_CMD, script_path],
            input=input_string,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            cwd=CWD
        )

        # Log the results
        #print(f"Debug: Script output: {result.stdout}")
        if result.returncode == 0:
            Log.info(f"Script executed successfully: {script_path}")
        else:
            Log.error(f"Script failed with return code {result.returncode}. Error: {result.stderr}")
    
    except subprocess.CalledProcessError as e:
        # Log any errors
        Log.error(f"Error running {script_path}: {e.stderr}")
        #print(f"Debug: Exception: {e}")
    except Exception as e:
        Log.error(f"Unexpected error running {script_path}: {e}")
        #print(f"Debug: Exception: {e}")

def check_and_trigger_update(isGFBuilding):
    global UPDATE_NEEDED
    timeoutSeconds = 10
    
    if isGFBuilding and UPDATE_NEEDED == True:
        Log.info("Godfinger change detected with isGFBuilding enabled. Triggering update...")

        # Run update_noinput.py
        update_script = os.path.abspath(os.path.join(os.getcwd(), "update", "update_noinput.py"))
        #print(f"Debug: Checking update script at {update_script}")
        run_script(update_script, ["Y", "Y", "Y"])

        # Run deployments_noinput.py with the same logic
        deploy_script = os.path.abspath(os.path.join(os.getcwd(), "update", "deployments_noinput.py"))
        #print(f"Debug: Checking deployments script at {deploy_script}")
        run_script(deploy_script, ["", "", ""])

        # Now, execute cleanup script based on the OS
        cleanup_script = os.path.abspath("cleanup.bat" if platform.system() == "Windows" else "cleanup.sh")
        #print(f"Debug: Cleanup script path: {cleanup_script}")
        
        try:
            result = subprocess.run(
                [cleanup_script],
                input="Y\n",
                text=True,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True
            )
            #print(f"Debug: Cleanup return code: {result.returncode}")
            #print(f"Debug: Cleanup stdout: {result.stdout}")
            #print(f"Debug: Cleanup stderr: {result.stderr}")

            if result.returncode == 0:
                Log.info(f"Cleanup script ({cleanup_script}) executed successfully.")
            else:
                Log.error(f"Error executing cleanup script: {result.stderr}")
        
        except Exception as e:
            Log.error(f"Exception occurred while running cleanup script: {e}")
            #print(f"Debug: Exception: {e}")
        
        # Force Godfinger to restart after update by crashing it
        Log.info("Auto-update process executed with predefined inputs. Restarting godfinger in ten seconds...")
        PluginInstance._serverData.API.Restart(timeoutSeconds)
    else:
        pass;

# Called once when this module ( plugin ) is loaded, return is bool to indicate success for the system
def OnInitialize(serverData : serverdata.ServerData, exports = None) -> bool:
    logMode = logging.INFO;
    if serverData.args.debug:
        logMode = logging.DEBUG;
    if serverData.args.logfile != "":
        logging.basicConfig(
        filename=serverData.args.logfile,
        level=logMode,
        format='%(asctime)s %(levelname)08s %(name)s %(message)s')
    else:
        logging.basicConfig(
        level=logMode,
        format='%(asctime)s %(levelname)08s %(name)s %(message)s')

    global SERVER_DATA;
    SERVER_DATA = serverData; # keep it stored
    if exports != None:
        pass;
    global PluginInstance;
    PluginInstance = gitTrackerPlugin(serverData)

    return True; # indicate plugin load success

# Called once when platform starts, after platform is done with loading internal data and preparing
def OnStart():
    global PluginInstance
    create_config_placeholder()
    check_git_installed()
    start_monitoring()
    startTime = time.time()
    loadTime = time.time() - startTime
    PluginInstance._serverData.interface.Say(PluginInstance._messagePrefix + f"Git Tracker started in {loadTime:.2f} seconds!")
    return True; # indicate plugin start success

# Called each loop tick from the system, TODO? maybe add a return timeout for next call
def OnLoop():
    pass

# Called before plugin is unloaded by the system, finalize and free everything here
def OnFinish():
    pass;

# Called from system on some event raising, return True to indicate event being captured in this module, False to continue tossing it to other plugins in chain
def OnEvent(event) -> bool:
    #print("Calling OnEvent function from plugin with event %s!" % (str(event)));
    if event.type == godfingerEvent.GODFINGER_EVENT_TYPE_MESSAGE:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTCONNECT:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENT_BEGIN:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTCHANGED:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTDISCONNECT:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_SERVER_EMPTY:
        _, _, _, svnPostHookFile, isSVNBuilding, isGFBuilding = load_config()
        CheckForSVNUpdate(isSVNBuilding, svnPostHookFile)
        check_and_trigger_update(isGFBuilding)
        UPDATE_NEEDED = False
        return UPDATE_NEEDED, False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_INIT:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_SHUTDOWN:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_KILL:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_PLAYER:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_EXIT:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_MAPCHANGE:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_SMSAY:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_POST_INIT:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_REAL_INIT:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_PLAYER_SPAWN:
        return False;

    return False;
