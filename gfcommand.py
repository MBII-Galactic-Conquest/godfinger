from typing import Any, Self;


class CommandParam():

    TYPE_NONE       =   -1;
    TYPE_INTEGER    =    0;
    TYPE_STRING     =    1;
    TYPE_BOOL       =    2;
    TYPE_FLOAT      =    3;
    TYPE_UNSIGNED   =    4;

    def __init__(self, name : str = None, position : int = -1, t : int = TYPE_NONE):
        self._name = name;
        self._argType = t;
        self._position = position;
        self._isOptional = self._position == -1; # either positional, or optional
        
    def GetName(self) -> str:
        if self._name == None:
            return None;
        else:
            return "" + self._name;

    def IsParamless(self) -> bool:
        return self._argType == CommandParam.TYPE_NONE;

    def GetPosition(self) -> int:
        return self._position;

    def IsOptional(self) -> bool:
        return self._isOptional;

class CommandArgs():
    def __init__(self):
        self._args = None;

class Command():
    def __init__(self, prefix : str, name : str):
        self._prefix = prefix;
        self._name = name;
        self._optionalParams : dict[str, CommandParam] = {};
        self._positionalParams = [];
        self._func = None;
        self._lastPositional = 0;
        self._paramCount = 0;

    def Param(self, name : str = None, ptype : int = CommandParam.TYPE_NONE) -> Self:
        if name != None:
            if not name.startswith("-"):
                print("Parameter with name %s should start with \"-\" or \"--\" for arg and argless parameters respectively" % name);
                return self;
            if name.startswith("--") and t != CommandParam.TYPE_NONE:
                print("Parameter with name %s is passed to add as argless but it actually expects a argument" % name);
                return self;
            if name not in self._optionalParams:
                self._optionalParams[name] = CommandParam(name, -1, ptype);
        else:
            # positional nameless param
            self._positionalParams.append(CommandParam(position = self._lastPositional, t = ptype));
            self._lastPositional += 1;
        return self;

    def Func(self, fn : any) -> Self:
        self._func = fn;
        return self;

    def GetName(self) -> str:
        return "" + self._name;

    def IsParameterless(self) -> bool:
        return len(self._positionalParams) == 0;

    
    def IsPrefix(self, pref : str) -> bool:
        return self._prefix.startswith(pref);

    def Invoke(self):
        if self._func != None:
            self._func();

class CommandParser():
    def __init__(self):
        pass;

class CommandManager():
    def __init__(self):
        self._commands : dict[str, Command] = {};

    def AddCommand(self, cmd : Command):
        name = cmd.GetName();
        if name not in self._commands:
            self._commands[name] = cmd;
        return self;

    def GetCommand(self, name : str) -> Command:
        if name in self._commands:
            return self._commands[name];
        return None;


def TestArgumentsFunc(argi, args, argb, argf, argu):
    print("\nArg test func called with %i %s %b %f %u" % argi, args, argb, argf, argu);

def TestHelpFunc():
    print("\nHelp function called, and you have been helped.");

if __name__ == "__main__":
    cmdManager = CommandManager();
    cmdManager.AddCommand(Command("!","--help").Func(TestHelpFunc));
    cmdManager.GetCommand("--help").Invoke();
    cmdManager.AddCommand(Command("!","test").Param(ptype = CommandParam.TYPE_INTEGER)\
                                         .Param(ptype = CommandParam.TYPE_STRING)\
                                         .Param(ptype = CommandParam.TYPE_BOOL)\
                                         .Param(ptype = CommandParam.TYPE_FLOAT)\
                                         .Param(ptype = CommandParam.TYPE_UNSIGNED));
    cmdManager.GetCommand("test").Invoke();