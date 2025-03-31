
import logging;
import godfingerEvent;
import pluginExports;
import lib.shared.serverdata as serverdata

SERVER_DATA = None;

# DISCLAIMER : DO NOT LOCK ANY OF THESE FUNCTIONS, IF YOU WANT MAKE INTERNAL LOOPS FOR PLUGINS - MAKE OWN THREADS AND MANAGE THEM, LET THESE FUNCTIONS GO.

Log = logging.getLogger(__name__);

def MyCoolFunction() -> int:
    return 1337;

class MyVariables():
    def __init__(self):
        self.myCoolVariable = 0;

MyCoolVariablesTable : MyVariables = MyVariables();

# Called once when this module ( plugin ) is loaded, return is bool to indicate success for the system
def OnInitialize(serverData : serverdata.ServerData, exports = None) -> bool:
    # Just an example how to configure the logger, otherwise it's using top-level configured logger.
    # logMode = logging.INFO;
    # if serverData.args.debug:
    #     logMode = logging.DEBUG;
    # if serverData.args.logfile != "":
    #     logging.basicConfig(
    #     filename=serverData.args.logfile,
    #     level=logMode,
    #     format='%(asctime)s %(levelname)08s %(name)s %(message)s')
    # else:
    #     logging.basicConfig(
    #     level=logMode,
    #     format='%(asctime)s %(levelname)08s %(name)s %(message)s')

    global SERVER_DATA;
    SERVER_DATA = serverData; # keep it stored
    if exports != None:
        # e.g
        exports.Add("MyCoolFunction", MyCoolFunction);
        # Primitive variables are passed by assigment, not reference, so you'd better wrap your values in some kind of export data class to make it work.
        exports.Add("MyCoolVariables", MyCoolVariablesTable, isFunc = False);
        pass;
    return True; # indicate plugin load success

# Called once when platform starts, after platform is done with loading internal data and preparing
def OnStart():
    # You can get your cross plugin dependancies here, e.g
    targetPlug = SERVER_DATA.API.GetPlugin("plugins.shared.test.testPlugin");
    if targetPlug != None:
        xprts = targetPlug.GetExports();
        if xprts != None:
            myCoolFunction = xprts.Get("MyCoolFunction").pointer;
            myCoolVars : MyVariables = xprts.Get("MyCoolVariables").pointer;
            #Log.debug("Testing Exports variable value %d", myCoolVars.myCoolVariable);
            myCoolVars.myCoolVariable = myCoolFunction(); # Execute it, if you want, or store for future use.
            #Log.debug("Testing Exports variable value %d", myCoolVars.myCoolVariable);
            myCoolVars = xprts.Get("MyCoolVariables").pointer;
            #Log.debug("Testing Exports variable value %d", myCoolVars.myCoolVariable);
        else:
            Log.error("Failure at importing API from testPlugin.");
            return False;
    else:
        Log.error("Failure in getting testPlugin.");
        return False;
    return True; # indicate plugin start success

# Called each loop tick from the system, TODO? maybe add a return timeout for next call
def OnLoop():
    pass
    #print("Calling Loop function from plugin!");

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