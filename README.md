# ㅤㅤㅤMBII OpenJK "Godfinger" scripting platform

</br>

ㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤ![GC logo](https://github.com/MBII-Galactic-Conquest/clientize/blob/main/gc.png)

</br>

A modular script system that allows rcon hookup &amp; plugin interaction to simplify serverside external scripting for MBII OpenJK in python.

```
The possibilities of this system allow for myriad of custom logfile implements, such as:

- moderation,
- kill tracking,
- points tracking,
- teamconfig management,
- custom gamemodes,
- round information,
- rcon chat injection,
- smod smsay chat commands,
- account systems,
- discord integration, & more.
```

</br>

</br>

This system is used originally for the [`MBII Supremacy Project`](https://community.moviebattles.org/threads/supremacy-release-tracker.10667/) now available for public use.

Originally created by [`ViceDice`](https://github.com/ViceDice) & [`ACHUTA`](https://github.com/mantlar), redistributed for a public MIT release.

All bugfixes or optimizations may be reviewed and potentially accepted through method of [`pull requests.`](https://github.com/MBII-Galactic-Conquest/godfinger/pulls)

We will not accept custom plugins in the form of pull requests, outside of crucial widespread plugins like `RTV.`

If you wish to dl & use `RTV` as a plugin, download the [release](https://github.com/MBII-Galactic-Conquest/godfinger/releases) for that branch, or you may view the branch [remotely.](https://github.com/MBII-Galactic-Conquest/godfinger/tree/plugins/rtv)

</br>

</br>

`** REQUIRES PYTHON 3.11+ **`

Ensure your logfile is set to `server.log` in your `server.cfg`

Ensure `g_logExplicit` is `"3"`, `g_logSync` is `"1"`, `com_logChat` is `"2"`, and `g_logClientInfo` is `"1"` in your `server.cfg`

Execute `"prepare.bat"` to install dependancy modules, sufficiently fill out `config jsons`, then just start the `"startRefactor.bat"`


</br>
</br>


### **Known problems**

#1) File backwards reading module in original form doesnt support ANSI-WIN1252 text encoding that is used by the MBIIServer to log stuff, until this dependancy is resolved via any means, manual modification is required, results are untested.

```
AppData\Local\Programs\Python\Python312\Lib\site-packages\file_read_backwards\file_read_backwards.py

supported_encodings = ["utf-8", "ascii", "latin-1", "ansi"]
```

</br>

### **Config file documentation**

The JSON file format is used for all config files included in this release, and while its usage is convenient for the programmers, it does not allow for in-line commentary to describe the function and usage of various settings in the file. Thus, the following is a brief overview of the config files included in this release.

</br>

### **godfingerCfg.json**
```
- "Remote"
    - "address"
        - "ip" : The IP address of the server to connect to. In most cases this should be localhost as the script requires access to the log file to function.
        - "port" : The port to connect to. In most cases, should be 29070.
    - "bindAddress" : The address for the script to use as a bind address. In most cases should be the same as the IP.
    - "password" : The server's rcon password. Set in server.cfg.
- "MBIIPath" : File path to the MBII installation to be used.
- "logFilename" : Name of the server log file (defined in server.cfg, default is server.log)
- "serverFileName" : Name of the server executable file to use.
- "logicDelay" : Interval of time to pass between script heartbeat loops.
- "logReadDelay" : Interval of time to pass between retrieval of new log lines to parse.
- "restartOnCrash" : If this is set to true, the server will attempt to restart itself if a fatal exception is detected.
- "Plugins": A list of plugin names, defined as python package strings (https://docs.python.org/3/tutorial/modules.html#packages), to use with the engine.
```

</br>

### **Implementing your own plugins**
```
    "Plugins":
    [
        {
            "path":"plugins.pluginfolder.pluginfile"
        }
    ]
}

- "plugins" : do not modify, native plugins dirpath
- "pluginfolder" : name of your custom plugin folder
- "pluginfile" : name of your custom plugin file, do not add .py extension
```

[Example of test plugin integration](https://github.com/MBII-Galactic-Conquest/godfinger/blob/main/plugins/test/testPlugin.py)
