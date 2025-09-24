import sqlite3;


class ADatabase():
    def __init__(self, path : str, name : str):
        self._name : str = name;
        self._path : str = path;

    def IsOpened(self) -> bool:
        pass;
    
    def Open(self) -> bool:   
        pass;
    
    def Close(self):
        pass;

    def ExecuteQuery(self, query : str):
        pass;
    
    def FetchQuery(self):
        print("Fetch query unimplemented");
    
    def LoadExtension(self, extpath : str):
        pass;

    def GetName(self) -> str:
        return self._name;

# Good enough, but not good in general.
class DatabaseLite(ADatabase):
    def __init__(self, path : str, name : str):
        super().__init__(path, name);
        self._connection = None;

    def IsOpened(self) -> bool:
        return self._connection != None;

    def Open(self) -> bool:
        if self.IsOpened():
            self.Close();
        self._connection = sqlite3.connect(self._path);
        if self.IsOpened():
            return True;
        else:
            return False;

    def Close(self):
        if self.IsOpened():
            self._connection.close();
            self._connection = None;

    def ExecuteQuery(self, query : str, withResponse = False) -> list[any]:
        if self.IsOpened():
            cursor = self._connection.cursor();
            cursor.execute(query);
            self._connection.commit();
            if withResponse:
                a = cursor.fetchall();
                cursor.close()
                return a
            else:
                cursor.close()
                return None;
        return None;

    def LoadExtension(self, extpath  : str): # Will work only if python is compiled with --enable-loadable-sqlite-extensions flag, it's not for distributions.
        if self.IsOpened():
            print("Loading db ext : " + extpath);
            self._connection.enable_load_extension(True)
            self._connection.load_extension(extpath);
            self._connection.enable_load_extension(False)

class DatabaseManager():

    DBM_RESULT_ERROR = -2;
    DBM_RESULT_ALREADY_EXISTS = -1;
    DBM_RESULT_OK = 0;
    

    def __init__(self):
        self._databases : dict[str, ADatabase] = {};
    
    def __del__(self):
        for k in self._databases:
            db = self._databases[k];
            db.Close();

    def GetDatabase(self, name : str) -> ADatabase:
        if name in self._databases:
            return self._databases[name];
        else:
            return None;

    def AddDatabase(self, db : ADatabase) -> int:
        if self.GetDatabase(db.GetName()) != None:
            return DatabaseManager.DBM_RESULT_ALREADY_EXISTS;
        else:
            self._databases[db.GetName()] = db;
            return DatabaseManager.DBM_RESULT_OK;

    def CreateDatabase(self, path : str, name : str) -> int:
        """
        Creates a database
        Created databases will keep their connections opened 

        :param path: A path to database
        :param name: A name of database for internal storage and referencing, used in searching

        :return: DBM_RESULT_OK | DBM_RESULT_ALREADY_EXISTS | DBM_RESULT_ERROR
        """
        if self.GetDatabase(name) != None:
            return DatabaseManager.DBM_RESULT_ALREADY_EXISTS;
        else:
            newdb = DatabaseLite(path, name);
            if newdb.Open():
                self.AddDatabase(newdb);
            else:
                return DatabaseManager.DBM_RESULT_ERROR;
            return DatabaseManager.DBM_RESULT_OK;