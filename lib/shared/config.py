
import json;
from typing import Self;
import logging;

Log = logging.getLogger(__name__);

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
            Log.debug(f"Attempting to load config from: {jsonPath}")
            with open(jsonPath) as file:
                config = json.load(file)        
                cls = cls()
                cls.cfg = config
                Log.info(f"Successfully loaded config from: {jsonPath}")
                # if validate == True and default != None: # todo
                #         if not Config.ValidatePropsStr(cls, default):
                #             print("Unable to validate property list of loaded config : %s" % jsonPath);
                #             raise Exception;
                return cls
        except FileNotFoundError:
            Log.warning(f"Config file not found: {jsonPath}")
            if default == None:
                return None
            else:
                Log.info(f"Creating default config file: {jsonPath}")
                cls = Config.FromJSONString(default);
                f = open(jsonPath, "wt")
                f.write(default)
                f.close()
                Log.info(f"Default config file created: {jsonPath}")
                return cls;
        except json.JSONDecodeError as e:
            Log.error(f"Invalid JSON in config file {jsonPath}: {e}")
            if default == None:
                return None
            else:
                Log.info(f"Using default config due to JSON error in: {jsonPath}")
                cls = Config.FromJSONString(default);
                f = open(jsonPath, "wt")
                f.write(default)
                f.close()
                Log.info(f"Default config file created to replace invalid JSON: {jsonPath}")
                return cls;
        except Exception as e:
            Log.error(f"Unexpected error loading config from {jsonPath}: {e}")
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
            try:
                Log.debug("Creating config from JSON string")
                config = json.loads(target);
                cls = cls();
                cls.cfg = config;
                Log.debug("Successfully created config from JSON string")
                return cls;
            except json.JSONDecodeError as e:
                Log.error(f"Invalid JSON string provided: {e}")
                return None;
            except Exception as e:
                Log.error(f"Unexpected error creating config from JSON string: {e}")
                return None;
        Log.warning("Attempted to create config from None JSON string")
        return None;
        
    def GetValue(self, paramName : str, defaultValue : any):
        if paramName in self.cfg:
            Log.debug(f"Retrieved config value for '{paramName}': {self.cfg[paramName]}")
            return self.cfg[paramName];
        else:
            Log.debug(f"Config parameter '{paramName}' not found, using default value: {defaultValue}")
            return defaultValue;

    @staticmethod
    def ValidatePropsStr(cfg : Self, target : str) -> bool:
        if target != None:
            Log.debug("Validating config properties from string")
            temp = Config.FromJSONString(target);
            if temp != None:
                result = Config.ValidateProps(cfg, temp);
                del temp;
                return result;
        Log.warning("Cannot validate properties: target string is None")
        return False;
        

    @staticmethod
    def ValidateProps(cfg : Self, target : Self) -> bool:
        Log.debug("Starting config properties validation")
        leftVars = cfg.__dict__.keys()
        rightVars = target.__dict__.keys()
        for lVar in leftVars:
            Log.debug("Props validate : " + lVar);
        Log.debug("Config properties validation completed")
        return True;
