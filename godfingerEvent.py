
import lib.shared.client as client;
import lib.shared.teams as teams;

GODFINGER_EVENT_TYPE_MESSAGE            = 1; # MessageEvent : client : client.Client, message : str, data["mesageRaw"] : line containing whole string of message including technical details
GODFINGER_EVENT_TYPE_INIT               = 2; # No need for own class, uses Event, data["vars"] : contains a dictionary with key-value pairs that are used to configurate server on init
GODFINGER_EVENT_TYPE_SHUTDOWN           = 3; # No need for own class, uses Event
GODFINGER_EVENT_TYPE_CLIENTCONNECT      = 4; # ClientConnectEvent : client = client instance that was connected, created and managed by the platform before plugins call
GODFINGER_EVENT_TYPE_CLIENTDISCONNECT   = 5; # ClientDisconnectEvent : client = client instance that was disconnected, deleted after all plugins finish with this kind of event
GODFINGER_EVENT_TYPE_CLIENTCHANGED      = 6; # ClientChangedEvent : client = client instance that was changed, data : dict of old data in key-value pairs, possible keys "team", "ja_guid", "name"
GODFINGER_EVENT_TYPE_KILL               = 7; # ClientKIllEvent : killer : client, victim : client, weapon : str
GODFINGER_EVENT_TYPE_PLAYER             = 8; # A generic Player event ( starts with Player # @something ) data["text"] : event string
GODFINGER_EVENT_TYPE_EXIT               = 9; 
GODFINGER_EVENT_TYPE_MAPCHANGE          = 10; # MapChangeEvent : mapName : str, oldMapName : str
GODFINGER_EVENT_TYPE_SMSAY              = 11; # Smod say event, playerName : str, smodID : str, adminId : str, message : str, passes the smod access filtering before forming.
GODFINGER_EVENT_TYPE_POST_INIT          = 12; # An event that is always fired when Init events are all processed in plugins.
GODFINGER_EVENT_TYPE_REAL_INIT          = 13; # gsess mallocd message indicating the INIT is REAL, the first.
GODFINGER_EVENT_TYPE_PLAYER_SPAWN       = 14; # player spawned event, data : dict of vars
GODFINGER_EVENT_TYPE_CLIENT_BEGIN       = 15; # just a client begin signal, called each time the client window is refreshed ( post connect, spawn, team switch, maybe something else )

class Event():
    def __init__(self, type : int, data : dict):
        self.type = type;
        self.data = data;

class KillEvent(Event):
    def __init__(self, cl : client.Client, victimCl : client.Client, weaponStr : str, data : dict):
        self.client = cl;
        self.victim = victimCl;
        self.weaponStr = weaponStr;
        super().__init__(GODFINGER_EVENT_TYPE_KILL, data)

# Probably not required
class PlayerEvent(Event):
    def __init__(self, cl : client.Client, data : dict):
        self.client = cl;
        super().__init__(GODFINGER_EVENT_TYPE_PLAYER, data)

class PlayerSpawnEvent(Event):
    def __init__(self, cl : client.Client, data : dict):
        self.client = cl;
        super().__init__(GODFINGER_EVENT_TYPE_PLAYER_SPAWN, data)

class ExitEvent(Event):
    def __init__(self, data : dict):
        super().__init__(GODFINGER_EVENT_TYPE_EXIT, data)

class MessageEvent(Event):
    def __init__(self, cl : client.Client, message : str, data : dict, teamId = teams.TEAM_GLOBAL):
        self.client = cl;
        self.message = message;
        self.teamId = teamId;
        super().__init__(GODFINGER_EVENT_TYPE_MESSAGE, data);

class ClientConnectEvent(Event):
    def __init__(self, cl : client.Client, data : dict ):
        self.client = cl;
        super().__init__(GODFINGER_EVENT_TYPE_CLIENTCONNECT, data);

class ClientBeginEvent(Event):
    def __init__(self, cl : client.Client, data : dict ):
        self.client = cl;
        super().__init__(GODFINGER_EVENT_TYPE_CLIENT_BEGIN, data);

class ClientDisconnectEvent(Event):
    # clients disconnected with REASON_SERVER_SHUTDOWN are clients that are actually still active serverside until any other reason is fired
    REASON_SERVER_SHUTDOWN = 0; 
    REASON_NATURAL = 1;
    REASON_KICK = 2;
    REASON_BAN = 3;
    REASON_TIMEOUT = 4; # connection lost and timed out on await, usually due to crashes/network issues, not implemented, technically speaking, it's natural
    def __init__(self, cl : client.Client, data : dict, reason = REASON_NATURAL ):
        self.client = cl;
        self.reason = reason;
        super().__init__(GODFINGER_EVENT_TYPE_CLIENTDISCONNECT, data);

class ClientChangedEvent(Event):
    def __init__(self, cl : client.Client, data : dict ):
        self.client = cl;
        super().__init__(GODFINGER_EVENT_TYPE_CLIENTCHANGED, data);

class MapChangeEvent(Event):
    def __init__(self, mapName : str, oldMapName : str):
        self.mapName = mapName;
        self.oldMapName = oldMapName;
        super().__init__(GODFINGER_EVENT_TYPE_MAPCHANGE, {})

class SmodSayEvent(Event):
    def __init__(self, playerName : str, smodID : int, adminIP : str, message : str):
        self.playerName = playerName
        self.smodID = smodID
        self.adminIP = adminIP
        self.message = message
        super().__init__(GODFINGER_EVENT_TYPE_SMSAY, {})