

import os;
import zipfile;
import lib.shared.bindata as bindata;

class PK3Bindata(bindata.Bindata):
    def __init__(self, name, bytes, srcPk):
        super().__init__(name, bytes);
        self.srcPk = srcPk;

class Pk3():

    def __init__(self):
        self._filePath = None;
        self._zf = None;
        self._isLoaded = False;
        self._index = dict[ str, zipfile.ZipInfo ]();
    
    def GetPath(self):
        return "" + self._filePath;

    def Unload(self):
        self._isLoaded = False;
        self._zf = None;
        self._index.clear();

    # It doesnt really loads all contents of zipfile into memory, that would be a waste, instead it loads zip's index for lookup later
    def Load(self, filePath) -> bool:
        if self._isLoaded:
            if self._filePath != filePath:
                # different pk
                self.Unload();
                
        self._filePath = filePath;
        fileTup = os.path.splitext(filePath);
        if fileTup[1] == ".pk3":
            # its a pk3, son.
            if zipfile.is_zipfile(filePath):
                self._zf = zipfile.ZipFile(filePath);
                zContentInfoList = self._zf.infolist();
                for zInfo in zContentInfoList:
                    fname = zInfo.filename;
                    self._index[fname] = zInfo;
                self._isLoaded = True;
                return True;
        return False;

    def GetFilesIndex(self) -> dict[str, zipfile.ZipInfo]:
        return self._index.copy();

    def GetFilesByMatch(self, matchFunction ) -> list[PK3Bindata]:
        rslt = [];

        return rslt;

    # TODO
    def IsFileByMatch(self, matchFunction ) -> bool:
        return False;

    def GetFile(self, fileName) -> PK3Bindata:
        rslt = None;
        if self._isLoaded:
            if self.IsFile(fileName):
                stream = self._zf.open(self._index[fileName]);
                if stream != None:
                    rslt = PK3Bindata(fileName, stream.read(), self);
                    stream.close();
        return rslt;

    def IsFile(self, fileName) -> bool:
        return fileName in self._index;

    @staticmethod
    def IsPk3(filePath):
        return zipfile.is_zipfile(filePath);

class Pk3Manager():
    def __init__(self):
        self._dirs = [];
        self._pks : dict[str, Pk3]= {};
        self._isInit = False;
    
    def Initialize(self, dirs : list[str]):
        if not self._isInit:
            print("Initializing pk3 manager...")
            for dir in dirs:
                if os.path.isdir(dir):
                    self.LoadDir(dir);
                    for pk in self._pks:
                        print(self._pks[pk].GetPath());
            print("Cached %s pk3 archives." % (str(len(self._pks.keys()))));
            print("Pk3 manager initialized.");
            self._dirs.clear();
            self._dirs += dirs;
            self._isInit = True;
    
    def Unload(self, filePath):
        if filePath in self._pks:
            self._pks[filePath].Unload();
    
    def UnloadAll(self):
        for k in self._pks.keys:
            self._pks[k].Unload();

    def LoadPk3(self, filePath) -> bool:
        newPk = Pk3();
        if newPk.Load(filePath):
            self._pks[filePath] = newPk;
            return True;
        return False;

    def LoadDir(self, dir : str) -> bool:
        if os.path.isdir(dir):
            for file in os.listdir(dir):
                fileTup = os.path.splitext(file);
                if fileTup[1].lower() == ".pk3":
                    filePath = os.path.join(dir,file);
                    if Pk3.IsPk3(filePath):
                        self.LoadPk3(filePath);
        return True; # stub

    def GetPk3(self, filePath):
        if filePath in self._pks:
            return self._pks[filePath];
        return None;

    def GetAllPk3(self):
        return self._pks.copy();

    # THESE ARE PERF HEAVY
    # count = how much pks we want to get, 1 would mean first in reverse order, since load order is first to last, then active file is last to first.
    def GetPksWithFile(self, matchFunction, count = 1024) -> list[Pk3]: # returns a list of PK3s with queried files to search, order of appearance from last pk3 in load order to first.
        print("PK3Manager::GetPksWithFile is not implemented");
        return None;
        rslt = [];
        for k in reversed(self._pks.keys()):
            while count:
                currentPk3 = self._pks[k];
                if currentPk3.IsFileByMatch(matchFunction):
                    rslt.append(currentPk3);
                    count -= 1;
        return rslt;

    # THESE ARE PERF HEAVY
    # get all files from cached pks that pass matchfunction, order from last to first in load ordering
    def GetFiles(self, matchFunction, count = 1024) -> list[PK3Bindata]:
        print("PK3Manager::GetFiles is not implemented");
        return None;
        bindata = list[PK3Bindata]();
        for k in reversed(self._pks.keys()):
            while count:
                currentPk3 = self._pks[k];
                if currentPk3.IsFileByMatch(matchFunction):
                    rslt = currentPk3.GetFileByMatch(matchFunction);
                    count -= 1; 
        return bindata;

    # return first file with filepath within cached PKs
    def GetFile(self, filePath) -> bytes:
        rslt = bytes();
        for k in reversed(self._pks.keys()):
            currentPk3 = self._pks[k];
            if currentPk3.IsFile(filePath):
                rslt = currentPk3.GetFile(filePath); 
        return rslt;
        
