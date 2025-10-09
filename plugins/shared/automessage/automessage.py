
import logging;
import godfingerEvent;
import pluginExports;
import lib.shared.serverdata as serverdata
import os;
import lib.shared.config as config;
import threading;
import lib.shared.threadcontrol as threadcontrol;
import time;
import random;

SERVER_DATA = None;

CONFIG_DEFAULT_PATH = os.path.join(os.path.dirname(__file__), "automessageCfg.json");
CONFIG_FALLBACK = \
"""{
    "prefix":"^5[AutoMessage] ^7",
    "interval": 5,
    "allowLastMessageTwice" : false,
    "messages": [
        "Message 1",
        "Message 2",
        "Message 3",
        "Message 4",
        "Message 5"
    ]
}
"""
global AutomessageConfig;
AutomessageConfig = config.Config.fromJSON(CONFIG_DEFAULT_PATH, CONFIG_FALLBACK)

# DISCLAIMER : DO NOT LOCK ANY OF THESE FUNCTIONS, IF YOU WANT MAKE INTERNAL LOOPS FOR PLUGINS - MAKE OWN THREADS AND MANAGE THEM, LET THESE FUNCTIONS GO.

Log = logging.getLogger(__name__);

PluginInstance = None;

class Automessage():
    def __init__(self, serverData : serverdata.ServerData):
        self._serverData = serverData;
        self.config = AutomessageConfig;
        self._threadLock = threading.Lock();
        self._threadControl = threadcontrol.ThreadControl();
        self._thread = threading.Thread(target=self._main_thread, daemon=True, args=(self._threadControl, self.config.cfg["interval"]));
        self._allowLastMessageTwice = self.config.cfg["allowLastMessageTwice"]
        self._lastMessage = ""

    def Start(self) -> bool:
        self._thread.start();
        return True;

    def Finish(self):
        with self._threadLock:
            self._threadControl.stop = True;
    
    def SendAutoMessage(self):
        messages = self.config.cfg['messages']
        if len(messages) == 0:
            message = "Error: No messages configured in automessageCfg.json"
        elif len(messages) == 1:
            message = messages[0]
        else:
            message = random.choice(messages)
            if not self._allowLastMessageTwice:
                while message == self._lastMessage:
                    message = random.choice(messages)
        self._lastMessage = message
        self._serverData.interface.SvSay(self.config.cfg["prefix"] + message);

    def _main_thread(self, control, interval):
        while(True):
            stop = False;
            with self._threadLock:
                stop = control.stop;
            if stop == True:
                break;
            self.SendAutoMessage();
            time.sleep(interval);

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
    global PluginInstance;
    PluginInstance = Automessage(serverData);
    if exports != None:
        pass;
    return True; # indicate plugin load success

# Called once when platform starts, after platform is done with loading internal data and preparing
def OnStart():
    global PluginInstance;
    return PluginInstance.Start();

# Called each loop tick from the system, TODO? maybe add a return timeout for next call
def OnLoop():
    pass

# Called before plugin is unloaded by the system, finalize and free everything here
def OnFinish():
    global PluginInstance;
    PluginInstance.Finish();

# Called from system on some event raising, return True to indicate event being captured in this module, False to continue tossing it to other plugins in chain
def OnEvent(event) -> bool:
    return False; # Just skip all events
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