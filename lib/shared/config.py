
import json;



class Config(object):
    ''' 
    When instantiated directly, contains the default configuration.

    When instantiated with the fromJSON method, contains the configuration stored in the JSON file at the given file path.
    '''
    def __init__(self):
        self.cfg = {}

    @classmethod
    def fromJSON(cls, jsonPath, default : str = None):
        try:
            with open(jsonPath) as file:
                config = json.load(file)        
                cls = cls()
                cls.cfg = config
                return cls
        except:
            if default == None:
                return None
            else:
                config = json.loads(default);
                cls = cls();
                cls.cfg = config;
                f = open(jsonPath, "wt")
                f.write(default)
                f.close()
                return cls;
        
    def GetValue(self, paramName : str, defaultValue : any):
        if paramName in self.cfg:
            return self.cfg[paramName];
        else:
            return defaultValue;
