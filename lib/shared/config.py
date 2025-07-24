
import json;
from typing import Self;


class Config(object):
    ''' 
    When instantiated directly, contains the default configuration.

    When instantiated with the fromJSON method, contains the configuration stored in the JSON file at the given file path.
    '''
    def __init__(self):
        self.cfg = {}

    @classmethod
    def fromJSON(cls, jsonPath, default : str = None, validate : bool = True):
        try:
            with open(jsonPath) as file:
                config = json.load(file)        
                cls = cls()
                cls.cfg = config
                # if validate == True and default != None: # todo
                #         if not Config.ValidatePropsStr(cls, default):
                #             print("Unable to validate property list of loaded config : %s" % jsonPath);
                #             raise Exception;
                return cls
        except:
            if default == None:
                return None
            else:
                cls = Config.FromJSONString(default);
                f = open(jsonPath, "wt")
                f.write(default)
                f.close()
                return cls;

    @classmethod
    def FromJSONString(cls, target : str) -> Self:
        if target != None:
            config = json.loads(target);
            cls = cls();
            cls.cfg = config;
            return cls;
        return None;
        
    def GetValue(self, paramName : str, defaultValue : any):
        if paramName in self.cfg:
            return self.cfg[paramName];
        else:
            return defaultValue;

    @staticmethod
    def ValidatePropsStr(cfg : Self, target : str) -> bool:
        if target != None:
            temp = Config.FromJSONString(target);
            if temp != None:
                result = Config.ValidateProps(cfg, temp);
                del temp;
                return result;
        return False;
        

    @staticmethod
    def ValidateProps(cfg : Self, target : Self) -> bool:
        leftVars = cfg.__dict__.keys()
        rightVars = target.__dict__.keys()
        for lVar in leftVars:
            print("Props validate : " + lVar);
        return True;
