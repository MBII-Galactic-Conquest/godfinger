
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

    def __init__(self):
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
            self._val = s;

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