# ㅤㅤㅤMBII OpenJK "Godfinger" scripting platform

</br>

ㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤ![GC logo](https://github.com/MBII-Galactic-Conquest/godfinger/blob/main/gc.png)

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
> - "MBIIPath" : File path to the MBII installation to be used.
> - "logFilename" : Name of the server log file (defined in server.cfg, default is server.log)
> - "serverFileName" : Name of the server executable file to use.
> - "logicDelay" : Interval of time to pass between script heartbeat loops.
> - "logReadDelay" : Interval of time to pass between retrieval of new log lines to parse.
> - "paths" : A list of string paths to append to system path, used to pass import directories for dependancies of plugins and such.
> - "prologueMessage" : A string to post in svsay when the platform is up.
> - "epilogueMessage" : A string to post in svsay when the platform is finishing.
> - "restartOnCrash" : If this is set to true, the server will attempt to restart itself if a fatal exception is detected.
> - "Plugins": A list of plugin names, defined as python package strings (https://docs.python.org/3/tutorial/modules.html#packages), to use with the engine.
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
