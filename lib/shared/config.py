
import json;



class Config(object):
    ''' 
    When instantiated directly, contains the default configuration.

    When instantiated with the fromJSON method, contains the configuration stored in the JSON file at the given file path.
    '''
    def __init__(self):
        self.cfg = {}

    @classmethod
    def fromJSON(cls, jsonPath):
        try:
            with open(jsonPath) as file:
                config = json.load(file)        
                cls = cls()
                cls.cfg = config
                return cls
        except:
            return None