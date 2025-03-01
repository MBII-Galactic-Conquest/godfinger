import importlib.util
import pluginExports;
import logging;
import importlib;
import time;
import traceback;
import os;
import subprocess;
import sys;

Log = logging.getLogger(__name__);

class Plugin():

    def __init__(self, module):
        self._module = module;
        self._onInitialize = None;
        self._onStart = None;
        self._onLoop = None;
        self._onEvent = None;
        self._onFinish = None;
        self._isFinished = False;
        self._exports = pluginExports.ExportTable();

    def __del__(self):
        if not self._isFinished:
            self.Finish();
        if self._onLoop != None:
            del self._onLoop;
        if self._onEvent != None:
            del self._onEvent;
        if self._onInitialize != None:
            del self._onInitialize;
        if self._onStart != None:
            del self._onStart;
        if self._onFinish != None:
            del self._onFinish;
    
    def Inititalize(self, data : any) -> bool:
        loopFunc            = getattr(self._module, "OnLoop");
        onEventFunc         = getattr(self._module, "OnEvent");
        onInitializeFunc    = getattr(self._module, "OnInitialize");
        onStartFunc         = getattr(self._module, "OnStart");
        onFinishFunc        = getattr(self._module, "OnFinish");
        # assert loopFunc != None, "Missing OnLoop function in target module";
        # assert onEventFunc != None, "Missing OnEvent function in target module";
        # assert onInitializeFunc != None, "Missing OnInitialize function in target module";
        # if loopFunc != None and onEventFunc != None and onInitializeFunc != None:
        self._onInitialize = onInitializeFunc;
        self._onStart = onStartFunc;
        self._onLoop = loopFunc;
        self._onEvent = onEventFunc;
        self._onFinish = onFinishFunc;
        return self._onInitialize(data, self._exports);

    def Finish(self):
        Log.info("Finishing Plugin %s...", self._module.__name__);
        self._isFinished = True;
        self._onFinish();
        Log.info("Finished Plugin %s.", self._module.__name__);
    
    def Start(self) -> bool:
        startTime = time.time();
        Log.info("Starting Plugin %s.", self._module.__name__);
        rslt = self._onStart();
        if rslt:
            Log.info("Plugin %s has started in %.2f seconds." % (self._module.__name__, time.time() - startTime));
        return rslt;

    def Loop(self):
        try:
            self._onLoop();
        except Exception as ex:
            Log.error("Exception [%s] caught on Loop tick for plugin [%s]\n %s", str(ex), self._module.__name__, traceback.format_exc());

    def Event(self, event) -> bool:
        try:
            return self._onEvent(event);
        except Exception as ex:
            Log.error("Exception [%s] caught on Event call for plugin [%s]\n %s", str(ex), self._module.__name__, traceback.format_exc());
        finally:
            return False; 

    def GetExports(self):
        return self._exports.copy();

class PluginManager():
    def __init__(self):
        self._isInit = False;
        self._plugins = {};
        self._isFinished = False;

    def __del__(self):
        pass

    def Initialize(self, targetPlugins : list, data : any) -> bool:
        Log.info("Loading plugins...");
        totalLoaded = 0;
        for targetPlug in targetPlugins:
            plug = self.LoadPlugin(targetPlug["path"], data);
            if plug != None:
                self._plugins[targetPlug["path"]] = plug;
                totalLoaded += 1;
        Log.info("Loaded total %d plugins. "% (totalLoaded));
        self._isInit = True;
        return self._isInit;

    def Start(self) -> bool:
        rslt = True;
        for targetPlug in self._plugins:
            rslt = self._plugins[targetPlug].Start();
            if not rslt:
                Log.error("Failed to start a plugin.");
                return rslt;
        return rslt;

    def LoadPlugin(self, name, data : any):
        Log.info("Loading plugin %s...", name);
        plugin = None;
        plugSpec = importlib.util.find_spec(name);
        if plugSpec == None:
            Log.error("Unable to locate plugin %s" % name);
            return None;
        else:
            plugPath = plugSpec.origin;
            Log.debug("Full path to target module %s" % plugPath);
            dirPath = os.path.dirname(plugPath);
            rqsPath = os.path.join(dirPath, "requirements.txt");
            if os.path.exists(rqsPath):
                fr = open(rqsPath, "r");
                if fr != None:
                    lines = fr.readlines();
                    fr.close();
                    Log.debug("requirements content : %s "  % lines);
                    missing = [];
                    for dep in lines:
                        try:
                            dep = dep.replace('\n', '');
                            depSpec = importlib.util.find_spec(dep);
                            if depSpec == None:
                                Log.debug("Required module %s is not found in current environment install" % dep);
                                missing.append(dep);
                        except ModuleNotFoundError:
                            Log.debug("Required module %s is not found in current environment install" % dep);
                            missing.append(dep);
                    if len(missing) > 0:
                        Log.debug("Trying to install dependancies for %s" % name);
                        subprocess.check_call([sys.executable, "-m", "pip", "install",] + missing)
            else:
                Log.debug("Requirements file is not found, assuming no specific dependancies."); 
            
            mod = importlib.import_module(name, package=None);
            if mod != None:
                newPlug = Plugin(mod);
                startTime = time.time();
                rslt = newPlug.Inititalize(data);
                if rslt:
                    Log.info("Plugin %s has been Loaded and Initialized in %.2f seconds." % (mod.__name__, time.time() - startTime));
                    plugin = newPlug;
            else:
                Log.error("Plugin %s was unable to load." % (name));
            return plugin;

    def Finish(self):
        if not self._isFinished:
            Log.info("Finishing plugin manager...");
            for plugin in self._plugins:
                self._plugins[plugin].Finish();
            self._isFinished = True;
            Log.info("Finished plugin manager.");

    def Loop(self):
        for plugin in self._plugins:
            self._plugins[plugin].Loop();

    def Event(self, event):
        for plugin in self._plugins:
            if self._plugins[plugin].Event(event): # handle hard capture return
                return;

    def GetPlugin(self, plugName):
        if plugName in self._plugins:
            return self._plugins[plugName];
        else:
            return None;
