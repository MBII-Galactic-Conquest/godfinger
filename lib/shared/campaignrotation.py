import traceback


class CampaignRotation:
    def __init__(self, name, id, vars = {}, srcPk = None):
        self._id = id;
        self._srcPk = srcPk;
        self._filename = name.removesuffix(".mbcr");
        self._vars = vars;
        self._isLoaded = False;
    
    def __key(self):
        return (self._filename);

    def __hash__(self):
        return hash((self.__key()));

    # byte array loading, for archives and stuff in-memory, no streaming support yet, only bulk data blocks
    def LoadBytes(self, byte_buffer) -> bool: 
        strContents = byte_buffer.decode();
        lines = strContents.splitlines();
        for line in lines:
            splitted = line.strip().split();
            self._vars[splitted[0]] = splitted[1];
        self._isLoaded = True;
        return True;

    def LoadFromPk3(self, pk3Path, filename):
        return False; # TODO IMPLEMENT THIS

    def LoadFile(self, filename) -> bool:
        if not self._isLoaded:
            try:
                if filename.endswith("mbcr"):
                    f = open(filename, "rb");
                    if f !=  None:
                        rslt = self.LoadBytes(f.read());
                        f.close();
                        return rslt;
                else:
                    print("Wrong file extension for target file : " + filename);
                    return False;
            except Exception:
                print("Failed on opening file for campaign load " + filename);
                traceback.print_exc();
                return False;

    def IsFromPk3(self):
        return self._srcPk != None;

    def GetFilename(self):
        return "" + self._filename;

    def GetId(self) -> int:
        return self._id;