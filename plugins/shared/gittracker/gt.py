import logging;
import godfingerEvent;
import pluginExports;
import lib.shared.serverdata as serverdata
import lib.shared.colors as colors
import lib.shared.teams as teams
import lib.shared.client as client
import subprocess
import json
import sys
import os
import time
import shutil
import psutil
import requests
import threading
import platform

SERVER_DATA = None;
GODFINGER = "godfinger"
Log = logging.getLogger(__name__);

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "gtConfig.json");
PLACEHOLDER = "placeholder"
PLACEHOLDER_PATH = "path/to/bat/or/sh"
PLACEHOLDER_REPO = "placeholder/placeholder"
PLACEHOLDER_TOKEN = "placeholder"
PLACEHOLDER_BRANCH = "placeholder"
GITHUB_API_URL = "https://api.github.com/repos/{}/commits?sha={}"

UPDATE_NEEDED = False
FALSE_VAR = False

MANUALLY_UPDATED = False

def get_godfinger_rwd():
    return os.path.dirname(os.path.abspath(__file__))

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
        self._hardUpdateSetting = 0
        self._commandList = \
            {
                # commands and aliases must be tuples because lists are unhashable apparently
                # index 0 : tuple of aliases for each command
                # index 1: tuple of help string and handler function
                teams.TEAM_GLOBAL : {
                },
                teams.TEAM_EVIL : {
                },
                teams.TEAM_GOOD : {
                },
                teams.TEAM_SPEC : {
                }
            }
        self._smodCommandList = \
            {
                # same as above
                tuple(["gfupdate", "update"]) : ("!<gfupdate | update> - forcibly run godfinger updates and deployments while restarting", self.HandleUpdate),
                tuple(["gfrestart", "restart"]) : ("!<gfrestart | restart> - forcibly restart the godfinger script system, without updates", self.HandleRestart),
                tuple(["hardupdate", "hardupdate"]) : ("<0/1> - when set to 1, determines if the mbiided process is forcibly restarted when forcing updates", self.HandleHardUpdate),
                tuple(["build", "build"]) : ("!<build <git|svn|winscp> [true|false]> - Check or set build status for git, svn, or winscp", self.HandleBuilding)
            }
    
    def HandleUpdate(self, playerName, smodID, adminIP, cmdArgs):
        ID, NAME = self.fetch_client_info(playerName, smodID)
        if ID is None: 
            Log.error(f"Failed to resolve client info for '{playerName}'. Cannot send message.")
            return False

        if self._hardUpdateSetting == 1:
            self._serverData.interface.SvSay(self._messagePrefix + f"{NAME} has requested a hard restart!")
            Log.warning(f"SMOD '{playerName}' (ID: {smodID}, IP: {adminIP}) requested a hard restart!!")
        else:
            self._serverData.interface.SvSay(self._messagePrefix + f"{NAME} has requested a godfinger update.")
            Log.info(f"SMOD '{playerName}' (ID: {smodID}, IP: {adminIP}) requested godfinger update.")

        ForceUpdate(hard_update_override=self._hardUpdateSetting)

        self._serverData.interface.SvSay(self._messagePrefix + "^2Godfinger update process completed.")
        return True

    def HandleRestart(self, playerName, smodID, adminIP, cmdArgs):
        timeoutSeconds = 10

        ID, NAME = self.fetch_client_info(playerName, smodID)
        if ID is None: 
            Log.error(f"Failed to resolve client info for '{playerName}'. Cannot send message.")
            return False

        self._serverData.interface.SvSay(self._messagePrefix + f"{NAME} has requested a godfinger restart.")

        Log.info(f"SMOD '{playerName}' (ID: {smodID}, IP: {adminIP}) force restarted godfinger...")
        self._serverData.API.Restart(timeoutSeconds)
        return True

    def HandleHardUpdate(self, playerName, smodID, adminIP, cmdArgs):
        # cmdArgs will be something like ['!hardupdate', '0'] or ['!hardupdate', '1'] or ['!hardupdate']
        global MANUALLY_UPDATED

        ID, NAME = self.fetch_client_info(playerName, smodID)
        if ID is None: 
            Log.error(f"Failed to resolve client info for '{playerName}'. Cannot send message.")
            return False

        if len(cmdArgs) < 2:
            message = f"{self._messagePrefix}Current hard update mode: ^5{self._hardUpdateSetting} ^7Usage: ^5!hardupdate <0|1>"
            self._serverData.interface.SvTell(ID, message)
            Log.info(f"{playerName} checked hardupdate setting (current: {self._hardUpdateSetting}).")
            return True

        try:
            value = int(cmdArgs[1])
            if value == 0 or value == 1:
                self._hardUpdateSetting = value
                message = f"{self._messagePrefix}Hard update mode set to: ^5{self._hardUpdateSetting}"
                self._serverData.interface.SvTell(ID, message)
                Log.info(f"{playerName} set hardupdate mode to {value}.")
                if value == 1:
                    MANUALLY_UPDATED = True
                    return MANUALLY_UPDATED
                if value == 0:
                    MANUALLY_UPDATED = False
                    return MANUALLY_UPDATED
                return True
            else:
                # If it's a number but not 0 or 1
                message = f"{self._messagePrefix}^1Invalid value '{value}'. ^7Please use ^50 ^7or ^51."
                self._serverData.interface.SvTell(ID, message)
                Log.warning(f"{playerName} tried to set hardupdate to invalid value {value}.")
                return False
        except ValueError:
            message = f"{self._messagePrefix}^1Invalid argument '{cmdArgs[1]}'. ^7Please use ^50 ^7or ^51."
            self._serverData.interface.SvTell(ID, message)
            Log.warning(f"{playerName} tried to set hardupdate with non-numeric value '{cmdArgs[1]}'.")
            return False

    def HandleBuilding(self, playerName, smodID, adminIP, cmdArgs):
        ID, NAME = self.fetch_client_info(playerName, smodID)
        if ID is None: 
            Log.error(f"Failed to resolve client info for '{playerName}'. Cannot send message.")
            return False

        Log.info(f"SMOD '{playerName}' (ID: {smodID}, IP: {adminIP}) used build command.")

        if len(cmdArgs) < 2:
            message = f"{self._messagePrefix}^7Usage: ^5!build ^9<git|svn|winscp> ^3[true|false]"
            self._serverData.interface.SvTell(ID, message)
            Log.warning(f"{playerName} used !build without enough arguments.")
            return False

        component = cmdArgs[1].lower()
        config_key = None

        if component == "git":
            config_key = "isGFBuilding"
        elif component == "svn":
            config_key = "isSVNBuilding"
        elif component == "winscp":
            config_key = "isWinSCPBuilding"
        else:
            message = f"{self._messagePrefix}^1Invalid build component: '{component}'. ^7Use ^5git^7, ^5svn^7, or ^5winscp^7."
            self._serverData.interface.SvTell(ID, message)
            Log.warning(f"{playerName} tried to set build for an unknown component: '{component}'.")
            return False
        
        current_config = load_config()
        if not current_config:
            Log.error(f"Failed to load configuration for !build command.")
            self._serverData.interface.SvTell(ID, f"{self._messagePrefix}^1Error: Could not load configuration.")
            return False

        # If a value is provided
        if len(cmdArgs) >= 3:
            value_str = cmdArgs[2].lower()
            new_value = None
            if value_str == "true":
                new_value = True
            elif value_str == "false":
                new_value = False
            else:
                message = f"{self._messagePrefix}^1Invalid value '{value_str}'. ^7Please use ^5true ^7or ^5false."
                self._serverData.interface.SvTell(ID, message)
                Log.warning(f"{playerName} tried to set build status to an invalid value '{value_str}'.")
                return False
            
            # Update the config in memory
            current_config[config_key] = new_value
            
            if write_config(current_config):
                message = f"{self._messagePrefix}Build status for ^5{component}^7 set to: ^5{new_value}"
                self._serverData.interface.SvTell(ID, message)
                Log.info(f"{playerName} set build status for {component} to {new_value}.")
                return True
            else:
                self._serverData.interface.SvTell(ID, f"{self._messagePrefix}^1Error saving configuration.")
                Log.error(f"{playerName} failed to save config for !build {component} {new_value}.")
                return False
        else:
            # If no value is provided, just tell the current status
            current_status = current_config.get(config_key, False) # Default to False if key somehow missing
            message = f"{self._messagePrefix}Build status for ^5{component}^7 is: ^5{current_status}"
            self._serverData.interface.SvTell(ID, message)
            Log.info(f"{playerName} checked build status for {component} (current: {current_status}).")
            return True

    def fetch_client_info(self, playerName, smodID):
        connected_clients = None
        try:
            connected_clients = self._serverData.API.GetAllClients()
            Log.debug(f"Successfully retrieved all connected clients.")
        except AttributeError:
            Log.error("ServerData.API does not have a GetAllClients() method. "
                      "Cannot reliably find client by name for SvTell via iteration.")
            return smodID, playerName
        except Exception as e:
            Log.error(f"An unexpected error occurred while trying to get all clients: {e}")
            return smodID, playerName

        for cl in connected_clients:
            ID = cl.GetId()
            NAME = cl.GetName()

        return ID, NAME

    def HandleSmodCommand(self, playerName, smodID, adminIP, cmdArgs):
        command = cmdArgs[0]
        if command.startswith("!"):
            # TODO: Make this an actual config option
            if command.startswith("!"):
                command = command[len("!"):]
        for c in self._smodCommandList:
            if command in c:
                return self._smodCommandList[c][1](playerName, smodID, adminIP, cmdArgs)
        return False

    def OnSmsay(self, playerName, smodID, adminIP, message):
        message = message.lower()
        messageParse = message.split()
        return self.HandleSmodCommand(playerName, smodID, adminIP, messageParse)

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
                    "branch": PLACEHOLDER_BRANCH,
                    "token": PLACEHOLDER_TOKEN
                },
                {
                    "repository": PLACEHOLDER_REPO,
                    "branch": PLACEHOLDER_BRANCH,
                    "token": PLACEHOLDER_TOKEN
                }
            ],
            "refresh_interval": 60,
            "gfBuildBranch": PLACEHOLDER_BRANCH,
            "svnPostHookFile": PLACEHOLDER_PATH,
            "winSCPScriptFile": PLACEHOLDER_PATH,
            "isWinSCPBuilding": FALSE_VAR,
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
        if (repo["repository"] == PLACEHOLDER_REPO or
            repo["branch"] == PLACEHOLDER_BRANCH or
            repo["token"] == PLACEHOLDER_TOKEN):
            print("\nPlaceholders detected in gtConfig.json. Please update the file.")
            sys.exit(0)

    return {
        "repositories": config.get("repositories", []),
        "refresh_interval": config.get("refresh_interval"),
        "gfBuildBranch": config.get("gfBuildBranch"),
        "svnPostHookFile": config.get("svnPostHookFile"),
        "winSCPScriptFile": config.get("winSCPScriptFile"),
        "isWinSCPBuilding": config.get("isWinSCPBuilding"),
        "isSVNBuilding": config.get("isSVNBuilding"),
        "isGFBuilding": config.get("isGFBuilding"),
    }

def write_config(config_data):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config_data, f, indent=2)
        Log.info(f"Configuration saved to {CONFIG_FILE}")
        return True
    except Exception as e:
        Log.error(f"Failed to save configuration to {CONFIG_FILE}: {e}")
        return False

def get_json_file_name(repo_url, branch_name):
    repo_name = repo_url.split('/')[-1]
    return f"{repo_name}_{branch_name}.json"

def load_or_create_json(repo_url, branch_name):
    config_dir = os.path.join(os.path.dirname(__file__), "jsonstore")
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)

    # Ensure each repository gets its own .json file
    config_file = get_json_file_name(repo_url, branch_name)
    config_file_path = os.path.abspath(os.path.join(config_dir, config_file))

    if not os.path.exists(config_file_path):
        # Create new config file with placeholders
        default_config = {"last_hash": ""}
        with open(config_file_path, "w") as f:
            json.dump(default_config, f)
    else:
        pass  # No need to do anything if the file already exists
    
    # Load existing config data
    with open(config_file_path, "r") as f:
        config_data = json.load(f)
    
    last_hash = config_data.get("last_hash", "").strip().strip("'").strip('"')
    
    return last_hash, config_file_path

def save_json(config_file_path, commit_hash):
    with open(config_file_path, "r") as f:
        config_data = json.load(f)
    
    config_data["last_hash"] = commit_hash
    
    with open(config_file_path, "w") as f:
        json.dump(config_data, f, indent=4)

def update_json_if_needed(repo_url, branch_name, commit_hash, commit_message, isGFBuilding, gfBuildBranch):
    global PluginInstance
    global UPDATE_NEEDED

    # First, reset last_hash
    last_hash, config_file_path = load_or_create_json(repo_url, branch_name)
    repo_name = repo_url.replace("MBII-Galactic-Conquest/", "").replace("MBII-Galactic-Conquest/", "")
    
    # Trim whitespace from the values
    commit_hash = commit_hash.strip()[:7]
    commit_message = commit_message.strip()[:72]
    last_hash = last_hash.strip()[:7]

    #Log.info(f"Comparing commit info for {repo_url} ({branch_name}):")
    #Log.info(f"Last commit hash: {last_hash}")
    #Log.info(f"New commit hash: {commit_hash}")
    #Log.info(f"New commit message: {commit_message}")

    if last_hash == commit_hash:
        return

    # Check if the commit hash has changed for this specific repository
    if last_hash != commit_hash:
        # Only update if hash has changed
        save_json(config_file_path, commit_hash)
        full_message = f"^5{commit_hash} ^7- {repo_name}/{branch_name} - ^5{commit_message}"
        PluginInstance._serverData.interface.SvSay(PluginInstance._messagePrefix + full_message)
        PluginInstance._serverData.interface.SvSound("sound/sup/message.mp3")
        
        if isGFBuilding == True and UPDATE_NEEDED == False and GODFINGER in repo_name and gfBuildBranch in branch_name:
            PluginInstance._serverData.interface.SvSay(PluginInstance._messagePrefix + "^1[!] ^7Godfinger change detected, applying when all players leave the server...")
            Log.debug(f"Godfinger change intercepted, automatically building '{gfBuildBranch}' and private deployments when all players leave the server...")
            UPDATE_NEEDED = True
            return UPDATE_NEEDED
    else:
        return

def get_latest_commit_info(repo_url: str, branch: str, token: str):
    try:
        repo_name = repo_url.replace("https://github.com/", "").replace("http://github.com/", "")
        api_url = GITHUB_API_URL.format(repo_name, branch)
        
        #Log.info(f"Requesting commit info from GitHub API for {repo_name}, branch '{branch}'...")

        if token == "" or token == " " or token == "None":
            token = None

        if token is not None:
            headers = {
                "Authorization": f"token {token}"
            }
            response = requests.get(api_url, headers=headers)
        else:
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
                token = repo["token"]

                commit_hash, commit_message = get_latest_commit_info(repo_url, branch_name, token)

                if commit_hash and commit_message:
                    #Log.info(f"\nNew commit detected for repository {i} ('{branch_name}') in '{repo_url}':")
                    #Log.info(f"Hash: {commit_hash}")
                    #Log.info(f"Message: {commit_message}")

                    update_json_if_needed(repo_url, branch_name, commit_hash, commit_message, isGFBuilding, gfBuildBranch)

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

    script_path = os.path.abspath(os.path.join(os.getcwd(), svnPostHookFile)) if svnPostHookFile else None

    if svnPostHookFile == PLACEHOLDER_PATH:
        return;

    if isSVNBuilding:
        if not os.path.exists(script_path):
            if svnPostHookFile == PLACEHOLDER:
                return
            Log.info(f"SVN Post Hook file not found.")
            return
        if svnPostHookFile == PLACEHOLDER:
            return
        try:
            if script_path.endswith('.bat', '.script', '.cmd') and os.name == 'nt':  # Windows
                subprocess.run(script_path, shell=True, check=True, input="")
            elif script_path.endswith('.sh') and os.name != 'nt':  # Linux/macOS
                subprocess.run(["bash", script_path], check=True, input="")
            else:
                Log.error("Unsupported script type or OS")
            Log.info(f"Successfully executed SVN Update: {script_path}")
        except subprocess.CalledProcessError as e:
            Log.error(f"Error executing SVN Update: {e}")
    else:
        pass;

def CheckForWinSCPUpdate(isWinSCPBuilding, winSCPScriptFile):
    global UPDATE_NEEDED

# Used to check for WinSCP FTP updates as well, using script hooks #
# Excellent for syncing your server with the gamedata/ REMOTE #

    script_path = os.path.abspath(os.path.join(os.getcwd(), winSCPScriptFile)) if winSCPScriptFile else None

    if os.name != 'nt': # Windows
        return;

    if winSCPScriptFile == PLACEHOLDER_PATH:
        return;

    if isWinSCPBuilding:
        if not os.path.exists(script_path):
            if isWinSCPBuilding == PLACEHOLDER:
                return
            Log.info(f"WinSCP script file not found.")
            return
        if isWinSCPBuilding == PLACEHOLDER:
            return
        try:
            if script_path.endswith('.bat', '.script', '.cmd') and os.name == 'nt':  # Windows
                subprocess.run(script_path, shell=True, check=True, input="")
            else:
                Log.error("Unsupported script type or OS")
            Log.info(f"Successfully executed WinSCP Update: {script_path}")
        except subprocess.CalledProcessError as e:
            Log.error(f"Error executing WinSCP Update: {e}")
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

def CheckForGITUpdate(isGFBuilding):
    global UPDATE_NEEDED, MANUALLY_UPDATED
    timeoutSeconds = 10

    if isGFBuilding and UPDATE_NEEDED:
        Log.info("Godfinger change detected with isGFBuilding enabled. Triggering update...")

        # Run .update_noinput.py
        update_script = os.path.abspath(os.path.join(os.getcwd(), "update", ".update_noinput.py"))
        run_script(update_script, ["Y", "Y", "Y"])

        # Run .deployments_noinput.py with the same logic
        deploy_script = os.path.abspath(os.path.join(os.getcwd(), "update", ".deployments_noinput.py"))
        run_script(deploy_script, ["", "", ""])

        # Execute cleanup script based on the OS
        cleanup_script = os.path.abspath("cleanup.bat" if platform.system() == "Windows" else "cleanup.sh")

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

            if result.returncode == 0:
                Log.info(f"Cleanup script ({cleanup_script}) executed successfully.")
            else:
                Log.error(f"Error executing cleanup script: {result.stderr}")
        
        except Exception as e:
            Log.error(f"Exception occurred while running cleanup script: {e}")

        if not MANUALLY_UPDATED:
            # Force Godfinger to restart after update
            Log.info("Auto-update process executed with predefined inputs. Restarting godfinger in ten seconds...")
            PluginInstance._serverData.API.Restart(timeoutSeconds)
        else:
            pass;

    elif isGFBuilding and not UPDATE_NEEDED:
        Log.info("isGFBuilding is enabled. Checking automatically for latest deployment HEADs...")

        # Run .deployments_noinput.py
        deploy_script = os.path.abspath(os.path.join(os.getcwd(), "update", ".deployments_noinput.py"))
        run_script(deploy_script, ["", "", ""])

        # Execute cleanup script based on the OS
        cleanup_script = os.path.abspath("cleanup.bat" if platform.system() == "Windows" else "cleanup.sh")

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

            if result.returncode == 0:
                Log.info(f"Cleanup script ({cleanup_script}) executed successfully.")
            else:
                Log.error(f"Error executing cleanup script: {result.stderr}")
        
        except Exception as e:
            Log.error(f"Exception occurred while running cleanup script: {e}")

        if not MANUALLY_UPDATED:
            # Force Godfinger to restart after update
            Log.info("Auto-deploy process executed with predefined inputs, restarting in ten seconds...")
            PluginInstance._serverData.API.Restart(timeoutSeconds)
        else:
            pass;

def quickstart_win():
    rwd = get_godfinger_rwd()
    script_path = os.path.join(rwd, "quickstart_win.bat")
    Log.info(f"Attempting to run Windows quickstart script: {script_path}")

    if not os.path.exists(script_path):
        Log.error(f"Windows quickstart script not found at: {script_path}")
        return

    try:
        subprocess.Popen([script_path], shell=True)
        Log.info("Windows quickstart script launched successfully.")
    except Exception as e:
        Log.error(f"Failed to launch Windows quickstart script: {e}")

def quickstart_linux_macOS():
    rwd = get_godfinger_rwd()
    script_path = os.path.join(rwd, "quickstart_linux_macOS.sh")
    Log.info(f"Attempting to run Linux/macOS quickstart script: {script_path}")

    if not os.path.exists(script_path):
        Log.error(f"Linux/macOS quickstart script not found at: {script_path}")
        return

    try:
        os.chmod(script_path, 0o755)
        subprocess.Popen([script_path], shell=True)
        Log.info("Linux/macOS quickstart script launched successfully.")
    except Exception as e:
        Log.error(f"Failed to launch Linux/macOS quickstart script: {e}")

def ForceUpdate(hard_update_override):
    global UPDATE_NEEDED, MANUALLY_UPDATED

    rwd = get_godfinger_rwd()

    # Timeout for API.Restart calls
    timeoutSeconds = 10

    # An update is needed
    if not UPDATE_NEEDED and MANUALLY_UPDATED:
        UPDATE_NEEDED = True
        MANUALLY_UPDATED = True

    # Let's access what's stored in config
    _, _, _, svnPostHookFile, winSCPScriptFile, isWinSCPBuilding, isSVNBuilding, isGFBuilding = load_config()

    # Run all update checks
    CheckForSVNUpdate(isSVNBuilding, svnPostHookFile)
    CheckForWinSCPUpdate(isWinSCPBuilding, winSCPScriptFile)
    CheckForGITUpdate(isGFBuilding)

    # An update is no longer needed
    if UPDATE_NEEDED and MANUALLY_UPDATED:
        UPDATE_NEEDED = False
        MANUALLY_UPDATED = False

    if hard_update_override == 1:
        if execute_hard_restart(rwd):
            Log.info("Manual server restart launched. Exiting current Godfinger & MBIIdedicated server process.")
            sys.exit(0)
        else:
            Log.error("Manual server restart was not possible.")
            sys.exit(1)
    else:
        PluginInstance._serverData.API.Restart(timeoutSeconds)

    return UPDATE_NEEDED, MANUALLY_UPDATED

def execute_hard_restart(rwd):

    Log.debug("Manual restart attempted...")

    godfinger_dir = os.getcwd()
    manual_restart_script_path = os.path.abspath(os.path.join(godfinger_dir, 'lib', 'other', '.hardrestart.py'))

    if not os.path.exists(manual_restart_script_path):
        Log.error(f"Manual restart script not found: {manual_restart_script_path}. Cannot proceed with restart.")
        return False

    Log.info(f"Invoking manual restart script: {manual_restart_script_path}")
    
    try:
        if os.name == 'nt' or sys.platform.startswith('win'):
            command_string = f'cmd /c start "" "{PYTHON_CMD}" "{manual_restart_script_path}"'
            
            subprocess.Popen(
                command_string,
                shell=True,
                creationflags=subprocess.DETACHED_PROCESS
            )
        else:
            # For Linux/macOS, direct execution is usually sufficient
            subprocess.Popen([PYTHON_CMD, manual_restart_script_path])
        
        Log.info("Manual restart script initiated successfully.")
        return True
    except Exception as e:
        Log.error(f"Failed to invoke manual restart script: {e}")
        return False

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

    newVal = []
    rCommands = SERVER_DATA.GetServerVar("registeredCommands")
    if rCommands != None:
        newVal.extend(rCommands)
    for cmd in PluginInstance._commandList[teams.TEAM_GLOBAL]:
        for alias in cmd:
            if not alias.isdecimal():
                newVal.append((alias, PluginInstance._commandList[teams.TEAM_GLOBAL][cmd][0]))
    SERVER_DATA.SetServerVar("registeredCommands", newVal)

    newVal = []
    rCommands = SERVER_DATA.GetServerVar("registeredSmodCommands")
    if rCommands != None:
        newVal.extend(rCommands)
    for cmd in PluginInstance._smodCommandList:
        for alias in cmd:
            if not alias.isdecimal():
                newVal.append((alias, PluginInstance._smodCommandList[cmd][0]))
    SERVER_DATA.SetServerVar("registeredSmodCommands", newVal)

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
        _, _, _, svnPostHookFile, winSCPScriptFile, isWinSCPBuilding, isSVNBuilding, isGFBuilding = load_config()
        CheckForSVNUpdate(isSVNBuilding, svnPostHookFile)
        CheckForWinSCPUpdate(isWinSCPBuilding, winSCPScriptFile)
        CheckForGITUpdate(isGFBuilding)
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
        return PluginInstance.OnSmsay(event.playerName, event.smodID, event.adminIP, event.message);
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_POST_INIT:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_REAL_INIT:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_PLAYER_SPAWN:
        return False;

    return False;
