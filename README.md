# ㅤㅤㅤMBII OpenJK "Godfinger" scripting platform

</br>

ㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤ![GC logo](https://github.com/MBII-Galactic-Conquest/godfinger/blob/main/gc.png)

ㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤ![Windows Terminal](https://img.shields.io/badge/Windows%20Terminal-%234D4D4D.svg?style=for-the-badge&logo=windows-terminal&logoColor=white)	 		![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)	 		![Bash Script](https://img.shields.io/badge/bash_script-%23121011.svg?style=for-the-badge&logo=gnu-bash&logoColor=white)</br>
ㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤ		 				 				 				 				 				 			ㅤㅤㅤ![Windows](https://img.shields.io/badge/Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)	 				 				 			![macOS](https://img.shields.io/badge/mac%20os-000000?style=for-the-badge&logo=macos&logoColor=F0F0F0)	 		![Linux](https://img.shields.io/badge/Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black)


</br>

#### A modular script extension system that allows streamlined rcon &amp; plugin interaction to simplify serverside processing for MBII in python. Aimed to better equip server owners to improve their own creative works, and have more expression over their game servers.

```
The possibilities of this system allow for myriad of custom logfile implements, such as:

- moderation,
- translations,
- blacklisting,
- kill tracking,
- points tracking,
- complex teamconfig management,
- making custom gamemodes,
- organizing round information,
- fun interactions with chat,
- remote cvar injection,
- smod smsay admin chat commands,
- incorporating shell scripts,
- account systems,
- sql databases,
- AI responses,
- automated asset building,
- integrating other languages,
- discord integration, & more.
```

</br>

</br>

> [!IMPORTANT]
> [`** REQUIRES PYTHON 3.12.7+ **`](https://www.python.org/downloads/release/python-3127/)
>
> Ensure your logfile is set to `server.log` in your `server.cfg.`
> 
> Ensure `g_logExplicit` is `"3"`, `g_logSync` is `"1"`, `com_logChat` is `"2"`, and `g_logClientInfo` is `"1"` in your `server.cfg.`
> 
> Execute `"prepare"` script based on platform in  `./prepare/os` to install dependancy modules, run the `"start"` or `"startDebug"` script based on platform in `./start/os`, then sufficiently fill out the generated `godfingerCfg.json` in root directory.
>
> You may now `start` the godfinger system normally.


</br>

</br>

> [!NOTE]
> This system was created initially for the [`MBII Supremacy Project`](https://community.moviebattles.org/threads/supremacy-release-tracker.10667/), now available for public use.</br>Originally created by [`ViceDice`](https://github.com/ViceDice) & [`ACHUTA`](https://github.com/mantlar), redistributed for a public MIT release.
>
> All bugfixes or optimizations may be reviewed and potentially accepted through method of [`pull requests.`](https://github.com/MBII-Galactic-Conquest/godfinger/pulls)</br>All pull requests are asked to be directed at the [`merge`](https://github.com/MBII-Galactic-Conquest/godfinger/tree/merge) branch before tested approval into upstream `dev` or `main` branches.</br></br>We will not accept custom plugins upstream, outside of crucial widespread plugins like `RTV`, designed for abstract server hosting.

</br>
</br>

> [!CAUTION]
> ### **Known problems**
>
> </br>
>
> #1) Python has issues sometimes with dirpathing in json files, so double backslashes `\\` may be necessary.</br>e.g: `C:\\Program Files (x86)\\SteamCMD\\JKA\\Gamedata\\MBII\\`
>
>
> </br>
>
> #2) `138` is the maximum bytes for svsay, `993` for vstr, and `2048` for general rcon payload in MBII OpenJK.</br>Estimating roughly `5 rcon messages per 0.02 seconds` *( 20 milliseconds, 50 fps )*
> 
> > The rcon messaging if rate is limiting will block calling thread until next timeframe, because we have to send/recieve rcon messaging in sync mode.
> 
> > So i.e, if you send 6 rcons within 20 miliseconds frame time, it will send 5 and then wait for 20 milliseconds and send the 6th rcon afterwards.
>
> 
> </br>
>
> #3) If you don't have GIT natively installed when running the update process as a windows user, and it errors on portable install, `7z_portable.zip` is stored using Git LFS. You must [`download`](https://github.com/MBII-Galactic-Conquest/godfinger/blob/main/lib/other/win/7z_portable.zip) and place it in `./lib/other/win`, then run the update process again, or reference [`release`](https://github.com/MBII-Galactic-Conquest/godfinger/releases/) versions with 7Z portable file manager included natively.</br>
> > Alternatively, and for `UNIX` users, ensure [`GIT is installed`](https://git-scm.com/downloads/) before using the godfinger platform as a necessary precaution.
>

</br>

</br>

> [!NOTE]
> ### **Config file documentation**
>
> The JSON file format is used for all config files included in this release, and while its usage is convenient for the programmers, it does not allow for in-line commentary to describe the function and usage of various settings in the file. Thus, the following is a brief overview of the config files included in this release.
>
> </br>
>
> ### **godfingerCfg.json**
> ```
> - "Remote"
>    - "address"
>        - "ip" : The IP address of the server to connect to. In most cases this should be localhost as the script requires access to the log file to function.
>         - "port" : The port to connect to. In most cases, should be 29070.
>     - "bindAddress" : The address for the script to use as a bind address. In most cases should be the same as the IP.
>     - "password" : The server's rcon password. Set in server.cfg.
>
> - "MBIIPath" : File path to the MBII installation to be used.
> - "logFilename" : Name of the server log file (defined in server.cfg, default is server.log)
> - "serverFileName" : Name of the server executable file to use.
> - "logicDelay" : Interval of time to pass between script heartbeat loops.
> - "logReadDelay" : Interval of time to pass between retrieval of new log lines to parse.
> - "paths" : A list of string paths to append to system path, used to pass import directories for dependancies of plugins and such.
> - "restartOnCrash" : If this is set to true, the server will attempt to restart itself if a fatal exception is detected.
>
> - "interfaces"
>    - "pty" : Pseudo-terminal utilities (https://docs.python.org/3/library/pty.html), used to wrap the mbiided process.
>        - "target" : File path to the MBII dedicated server executable.
>         - "inputDelay" : Interval of time to pass between terminal heartbeat loops.
>    - "rcon" : The typical use of the godfinger script extension system, generic logfile parsing.
>     - "Remote"
>         - "address"
>            - "ip" : The IP address of the server to connect to. In most cases this should be localhost as the script requires access to the log file to function.
>            - "port" : The port to connect to. In most cases, should be 29070.
>       - "bindAddress" : The address for the script to use as a bind address. In most cases should be the same as the IP.
>       - "password" : The server's rcon password. Set in server.cfg.
>      - "logFilename" : Name of the server log file (defined in server.cfg, default is server.log)
>      - "logReadDelay" : Interval of time to pass between retrieval of new log lines to parse.
>     - "Debug"
>       - "TestRetrospect" : true/false allows for simulating and recreating active game data for the purpose of test case bugfixing. False is generally considered default.
>
> - "interface" : Where you can specify which interface you wish to use, in this case, "rcon" or "pty", with "rcon" as default.
>
> - "paths" : Where you can specify foreign directories not native to the godfinger root working directory, in the event of private codebases, or other implements with the godfinger system. Default is ".\\"
>
> - "prologueMessage" : String to show when the godfinger system has acknowledged sufficiently starting up, and deployed natively without error.
> - "epilogueMessage" : String to show when the godfinger system concludes, and has exited cleanly, safely.
>
> - "Plugins" : A list of plugin names, defined as python package strings (https://docs.python.org/3/tutorial/modules.html#packages), to use with the engine.
> ```

</br>

</br>

> [!IMPORTANT]
> ### **Implementing your own plugins**
> ```
>    "Plugins":
>    [
>        {
>            "path":"plugins.shared.pluginfolder.pluginfile"
>        }
>    ]
>}
>
> - "plugins" : do not modify, native plugins dirpath
> - "shared" : shared, or private directory, depending on plugins use
> - "pluginfolder" : name of your custom plugin folder
> - "pluginfile" : name of your custom plugin file, do not add .py extension
> ```
>
> > Ensure you place the `requirements.txt` with required dependencies alongside your plugins.
>
> [Example of test plugin integration](https://github.com/MBII-Galactic-Conquest/godfinger/blob/main/plugins/shared/test/testPlugin.py)

</br>

</br>

> [!IMPORTANT]
> ### **Deploying Private Codebases**
>
> You may deploy your own codebases, using [deploy keys](https://docs.gitlab.com/user/project/deploy_keys/), a feature of the Godfinger update system.
> 
> > Once running the `update` process, you will check automatically for deployments.</br>You may edit `deployments.env` once generated, to specify paths to your public SSH key.</br></br>e.g: `{user}/{repo}/{branch}=./key/{key}`</br></br>Anything other than placeholder generates a folder in `./update/deploy/<foldername>.`</br>This allows multiple deployments to be updated at the same time, so long as the SSH keys are valid.</br></br> It is generally good practice to safeguard config textassets from being overwritten.</br>By properly modifying a `.gitignore` in your private repository.
>
> You will have to integrate your changes within the paths in `godfingerCfg.json`, featuring:
>
> ```
>     "paths":
>    [
>        ".\\",
>        "<path>\\<to>\\<update>\\<deploy>\\<folder>\\"
>    ],
> ```
>

</br>

</br>

> [!IMPORTANT]
> ### **Using WinSCP Script Hooks**
>
> The godfinger system supports portable WinSCP script hook installation.
> 
> > You may sync your `gamedata/` directory on the `local` by pulling latest from the `REMOTE.`</br>Ensuring your latest .PK3 asset changes are synced to your game servers via `FTP.`</br></br>Running `installwinSCP_portable.bat` will install and generate a template `winscp_sync_gamedata.bat` file inside of your virtual environment, in `/venv/portable_winSCP.`
>
> You will have to modify the generated `winscp_sync_gamedata.bat` with the following:
>
> ```
>
> $ = your partition (e.g: D drive)
>
> SET "FTP_HOST=your_ftp_host.com"
> SET "FTP_USER=your_ftp_username"
> SET "FTP_PASS=your_ftp_password"
> SET "REMOTE_FTP_PATH=/path/on/ftp/server/to/files" # Usually, $:/FTP/ being $:/FTP/Gamedata
> # Do not touch local target path.
>
> ```
>
> **Using the [gittracker](https://github.com/MBII-Galactic-Conquest/godfinger/tree/main/plugins/shared/gittracker) plugin, read documentation, and set `isWinSCPBuilding` to `true`**

</br>

</br>

> [!IMPORTANT]
> ### **Utilizing Docker Containers**
>
> > Ensure you have [docker](https://docs.docker.com/get-started/get-docker/) installed before continuing</br>
> > `sudo apt install -y docker.io && pip install docker`
>
> You may utilize docker containers to isolate godfinger sessions on UNIX.<br>
> The godfinger system does not support local instancing, so docker is encouraged.
>
> ```
> 1) Installing Manually:
>
> Ensure you are in the godfinger RWD, one level above the docker/ folder...
>
> docker build -f docker/Dockerfile -t godfinger .
>
> docker run --rm -it \
> -v $(pwd)/../dockerize:/app/jediacademy \
> -v $(pwd):/app/jediacademy/gamedata/godfinger \
> -v $(pwd)/../configstore_godfinger:/app/jediacademy/gamedata/godfinger \
> -p 29070:29070/udp \
> -p 29070:29070/tcp \
> godfinger
>
> 2) Automated Local Install:
>
> chmod +x docker/build-image.sh
> cd docker/
> ./build-image.sh
>
> 3) Pterodactyl Egg:
>
> Access the Pterodactyl Panel as Admin,
> Admin Panel → Nests,
> Create a New Nest,
> Eggs → Create Egg,
> Import docker/godfinger-egg.json,
> Select Godfinger Egg and apply your Docker Image...
>
> ```
>
> <br>
>
> Ensure `Jedi Academy` & `Moviebattles II` is installed in a parent subdirectory called `dockerize/`<br>Recursive access to necessary linux server binaries is required for godfinger to run in automated containerized environments.<br>
>
> ```
> dockerize/
> └── gamedata/
> :   └── MBII/
> :
> godfinger/
> └── $(RWD/)
> ```
>
> <br>
>
> You will have to create your own `volumes`, or `svn post hooks` to serve as configstores for automation purposes.<br>Godfinger will still encounter exceptions requiring `config files` & `environment variables` to run without first time error.
>
> Ensure your configstore is placed in a parent subdirectory, called `configstore_godfinger/` mirroring pathing for the project.
>
> ```
> configstore_godfinger/
> ├── godfingerCFG.json
> └── plugins/
> :    ├── shared/
> :    └── myplugin/
> :        ├── pluginCFG.json
> :        └── envfile.env
> :
> godfinger/
> └── $(RWD/)
> ```
>
