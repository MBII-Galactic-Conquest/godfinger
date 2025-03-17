
import lib.shared.rcon as rcon;
import lib.shared.colors as colors;
import godfingerinterface;

class Cvar():

    CVAR_NONE           = 0x00000000;
    CVAR_ARCHIVE        = 0x00000001;
    CVAR_USERINFO       = 0x00000002;
    CVAR_SERVERINFO     = 0x00000004;
    CVAR_SYSTEMINFO     = 0x00000008;
    CVAR_INIT           = 0x00000010;
    CVAR_LATCH          = 0x00000020;
    CVAR_ROM            = 0x00000040;
    CVAR_USER_CREATED   = 0x00000080;
    CVAR_TEMP           = 0x00000100;
    CVAR_CHEAT          = 0x00000200;
    CVAR_NORESTART      = 0x00000400;
    CVAR_INTERNAL       = 0x00000800;
    CVAR_PARENTAL       = 0x00001000;
    CVAR_SERVER_CREATED = 0x00002000;
    CVAR_VM_CREATED     = 0x00004000;
    CVAR_PROTECTED      = 0x00008000;
    CVAR_NODEFAULT      = 0x00010000;

    class Flags():
        def __init__(self):
            self.field = 0;
    
        @staticmethod
        def CharToFlag(ch : str) -> int:
            if ch == "S":
                return Cvar.CVAR_SERVERINFO;
            elif ch == "s":
                return Cvar.CVAR_SYSTEMINFO;
            elif ch == "U":
                return Cvar.CVAR_USERINFO;
            elif ch == "R":
                return Cvar.CVAR_ROM;
            elif ch == "I":
                return Cvar.CVAR_INIT;
            elif ch == "A":
                return Cvar.CVAR_ARCHIVE;
            elif ch == "L":
                return Cvar.CVAR_LATCH;
            elif ch == "C":
                return Cvar.CVAR_CHEAT;
            elif ch == "?":
                return Cvar.CVAR_USER_CREATED;
            else:
                return Cvar.CVAR_NONE;

        def __str__(self):
            return f"Flags 0x{self.field:X}";
    
        def __repr__(self):
            return self.__str__();

    def __init__(self, manager : any):
        self._manager = manager; # actually a CvarManager, imagine we're casting;
        self._flags = Cvar.Flags();
        self._name = "";
        self._val = "";
    
    def IsFlag(self, flag):
        return ( self._flags.field & flag ) == flag;
    
    def GetName(self) -> str:
        return "" + self._name;

    def GetValue(self) -> str:
        return "" + self._val;

    def SetValue(self, v : any):
        s = str(v);
        if s != None:
            if self._val != s:
                self._val = s;
                self._manager.OnCvarChange(self);

    def FromCvarlistString(self, cvarStr):
        splitvarname = cvarStr.split("\"");
        for s in splitvarname:
            if s == "":
                splitvarname.remove(s);
        if len ( splitvarname ) > 0:
            splitVar = splitvarname[0].split();
            if len(splitVar) > 1:
                flagsList = splitVar[0:-2];
                for flag in flagsList:
                    self._flags.field |= Cvar.Flags.CharToFlag(flag);
                self._name = splitVar[-2];
                self._val  = splitvarname[-1];

    def __str__(self):
        return f"Cvar {self._name} : {self._val} {self._flags}";

    def __repr__(self):
        return self.__str__();


class CvarManager():
    def __init__(self, iface : godfingerinterface.IServerInterface):
        self._cvars = dict[str, Cvar]();
        self._iface = iface;
    
    def Initialize(self) -> bool:
        if self._iface == None:
            return False;
        else:
            self._FetchCvars();
            return True;

    def _FetchCvars(self):
        cvarStr = self._iface.CvarList();
        if cvarStr != "" and cvarStr != None:
            cvarsStr = colors.stripColorCodes(cvarStr);
            parsed = {};
            splitted = cvarsStr.splitlines();
            for line in splitted:
                cv = Cvar(self);
                cv.FromCvarlistString(line);
                parsed[cv.GetName()] = cv;
            for name in parsed:
                if name not in self._cvars:
                    self._cvars[name] = parsed[name];
                else:
                    self._cvars[name].SetValue(parsed[name].GetValue());

    def GetAllCvars(self) -> dict[str, Cvar]:
        return self._cvars.copy();

    def GetCvar(self, name : str) -> Cvar:
        if self.IsCvar(name):
            return self._cvars[name];
        else:
            return None;

    def IsCvar(self, name : str) -> bool:
        return name in self._cvars;

    def OnCvarChange(self, cvar : Cvar):
        self._iface.SetCvar(cvar.GetName(), cvar.GetValue());

