
import traceback;

class TeamConfig():
    
    def __init__(self, name = None, pathName = None):
        self._name = name;
        self._classesAllowedNum = 0;
        self._timePeriodNum = 0;
        self._EUAllowedNum = 0;
        self._classes = {};
        self._subClasses = {};
        self._isLoaded = False;
        self._pathName = pathName;
        self._filename = self.__FormatFilename(pathName);
    
    def __str__(self):
        return "Filename: %s\n Name : %s\n ClassesAllowed : %s\n TimePeriod : %s\n EUAllowed : %s\n Classes : %s\n Subclasses : %s"  % (self._filename, self._name, self._classesAllowedNum, self._timePeriodNum, self._EUAllowedNum, self._classes, self._subClasses);

    def __repr__(self):
        return self.__str__()
    
    def LoadBytes(self, byte_buffer) -> bool:
        if self._isLoaded:
            return True;
    
        strContents = byte_buffer.decode();
        lines = strContents.splitlines();
        for line in lines:
            line = line.strip();
            if len(line) < 1:
                continue; # skip empty lines 
            if line.startswith("/"): # skip / commented lines
                continue;
            if line.startswith("#"):
                continue; # skip # commented lines
            splitted = line.split();
            if len(splitted) > 1:
                paramName = splitted[0];
                paramValue = splitted[1];
                if paramName == "name":
                    self._name = paramValue;
                elif paramName == "ClassesAllowed":
                    self._classesAllowedNum = int(paramValue);
                elif paramName == "TimePeriod":
                    self._timePeriodNum = int(paramValue);
                elif paramName == "EUAllowed":
                    self._EUAllowedNum = int(paramValue);
                elif paramName.startswith("class"):
                    self._classes[paramName] = paramValue;
                elif paramName.startswith("Subclass"):
                    self._subClasses[paramName] = paramValue;

        self._isLoaded = True;

        return True;

    def LoadFile(self, pathName) -> bool:
        if not self._isLoaded:
            try:
                if pathName.endswith("mbtc"):
                    f = open(pathName, "rb");
                    if f !=  None:
                        rslt = self.LoadBytes(f.read());
                        f.close();
                        self._pathName = pathName;
                        self._filename = self.__FormatFilename(pathName);
                        return rslt;
                else:
                    print("Wrong file extension for target file : " + pathName);
                    return False;
            except Exception:
                print("Failed on opening file for teamconfig load " + pathName);
                traceback.print_exc()
                return False;
        return True;

    def __FormatFilename(self, pathName) -> str:
        pos = pathName.rfind("/");
        posf = pathName.rfind("\\");
        filename = "";
        if pos != -1:
            filename = pathName[pos+1:len(pathName)-5];
        elif posf != -1:
            filename = pathName[posf+1:len(pathName)-5];
        else:
            filename = pathName[0:-5];
        return filename;

    def GetFilename(self):
        if self._filename != None:
            return "" + self._filename;
        else:
            return None;

    def GetPathName(self):
        return "" + self._pathName;

    