from typing import Any, Self


class CommandParam():

    TYPE_NONE       =   -1
    TYPE_INTEGER    =    0
    TYPE_STRING     =    1
    TYPE_BOOL       =    2
    TYPE_FLOAT      =    3
    TYPE_UNSIGNED   =    4

    def __init__(self, t : int = TYPE_NONE):
        self._ptype = t

    def IsOptional(self) -> bool:
        return False

    def IsPositional(self) -> bool:
        return False

    def IsFlag(self) -> bool:
        return self._ptype == CommandParam.TYPE_NONE
    
class OptionalParam(CommandParam):
    def __init__(self, name : str = None, t : int = CommandParam.TYPE_NONE):
        super().__init__(t)
        self._name = name
        
    def GetName(self) -> str:
        if self._name == None:
            return None
        else:
            return "" + self._name

    def IsOptional(self) -> bool:
        return True

class PositionalParam(CommandParam):
    def __init__(self, position : int, t : int = CommandParam.TYPE_NONE):
        super().__init__(t)
        self._position = position

    def GetPosition(self) -> int:
        return self._position

    def IsPositional(self) -> bool:
        return True


class CommandArg():
    def __init__(self, name : str, value : any):
        self._name = name
        self._value = value

    def GetValue(self) -> any:
        return self._value

    def GetName(self) -> str:
        return self._name

    def IsPositional(self) -> bool:
        return self._name == None

class CommandArgs():
    def __init__(self, cmdName : str):
        self._cmdName = cmdName
        self._optional : dict[str, CommandArg]= {}
        self._positionalArgs : list[CommandArg] = []

    def GetName(self) -> str:
        return "" + self._cmdName

    def AddArg(self, arg : CommandArg):
        positional = arg.IsPositional()
        if positional:
            self._positionalArgs.append(arg)
        else:
            argName = arg.GetName()
            if argName not in self._optional:
                self._optional[argName] = arg
    
    def GetPositionalArg(self, position : int) -> CommandArg:
        if position < len(self._positionalArgs):
            return self._positionalArgs[position]
        else:
            return None

    def GetAllPositionalArgs(self) -> list[CommandArg]:
        return self._positionalArgs.copy()

    def GetOptionalArg(self, name) -> CommandArg:
        if name in self._optional:
            return self._optional[name]
        else:
            return None

    def Reset(self):
        self._optional.clear()
        self._positionalArgs.clear()

    def IsEmpty(self) -> bool:
        return len(self._positionalArgs) + len(self._optional) == 0

    def __repr__(self):
        res = "Positional:::\n"
        for pos in self._positionalArgs:
            res += pos.GetValue() + "\n"
        res += "Optional:::\n"
        for opt in self._optional:
            optional = self._optional[opt]
            res += optional.GetName() + " : " + str(optional.GetValue()) + "\n"
        return res


class Command():
    def __init__(self, prefix : str, name : str):
        self._prefix = prefix
        self._name = name
        self._optionalParams : dict[str, OptionalParam] = {}
        self._positionalParams = []
        self._func = None
        self._lastPositional = 0
        self._paramCount = 0

    def Param(self, name : str = None, ptype : int = OptionalParam.TYPE_NONE) -> Self:
        if name != None:
            if not name.startswith("-"):
                print("Parameter with name %s should start with \"-\" or \"--\" for arg and argless parameters respectively" % name)
                return self
            if name.startswith("--") and ptype != OptionalParam.TYPE_NONE:
                print("Parameter with name %s is passed to add as argless but it actually expects a argument" % name)
                return self
            if name not in self._optionalParams:
                self._optionalParams[name] = OptionalParam(name, ptype)
        else:
            # positional nameless param
            self._positionalParams.append(PositionalParam(position = self._lastPositional, t = ptype))
            self._lastPositional += 1
        return self

    def Func(self, fn : any) -> Self:
        self._func = fn
        return self

    def GetName(self) -> str:
        return "" + self._name

    def IsParamless(self) -> bool:
        return len(self._positionalParams) == 0

    def IsPrefix(self, pref : str) -> bool:
        return self._prefix.startswith(pref)

    def Invoke(self, cargs : CommandArgs):
        if self._func != None:
            self._func(cargs)
        else:
            print("ERROR : Command %s invoking without bound function handler." % self.GetName())

class CommandParser():
    def __init__(self, prefix : str):
        self._prefix = prefix
    
    def IsPositionalArg(self, token : str) -> bool:
        if not token.startswith("-"):
            return True
        else:
            return False

    def IsParamlessArg(self, token : str) -> bool:
        if token.startswith("--"):
            return True
        else:
            return False

    def IsOptionalArg(self, token : str) -> bool:
        if token.startswith("-"):
            return True
        else:
            return False

    # !SomeCommand -optional2 optional2Value arg1- -paramlessOptional3 arg2 -optional1 optional1Value --paramlessOptional arg3 
    # -> ! SomeCommand arg1 arg2 arg3 -optional1 optionalValue1 --paramlessOptional 
    def ParseCommand(self, cmd : str) -> CommandArgs:
        cargs = None
        if cmd != None:
            if cmd.startswith(self._prefix):
                splitted = cmd[len(self._prefix):].split()
                if len(splitted) > 0:
                    cargs = CommandArgs(splitted[0]) # 0 is the command name
                    i = 1
                    while(i < len(splitted)):
                        token = splitted[i]
                        if self.IsPositionalArg(token):
                            cargs.AddArg(CommandArg(None,token))
                            i += 1
                        elif self.IsOptionalArg(token):
                            if self.IsParamlessArg(token):
                                cargs.AddArg(CommandArg(token,None))
                                i += 1
                            else:
                                if len(splitted) > i + 1:
                                    cargs.AddArg(CommandArg(token, splitted[i+1]))
                                    i += 2
        return cargs


class CommandManager():
    def __init__(self):
        self._commands : dict[str, Command] = {}

    def AddCommand(self, cmd : Command):
        name = cmd.GetName()
        if name not in self._commands:
            self._commands[name] = cmd
        return self

    def GetCommand(self, name : str) -> Command:
        if name in self._commands:
            return self._commands[name]
        return None


def TestArgumentsFunc(cargs : CommandArgs):
    print("AAUUGHH")

def TestHelpFunc(cargs : CommandArgs):
    print("\nHelp function called, and you have been helped.")

if __name__ == "__main__":
    cmdManager = CommandManager()
    cmdParser = CommandParser("!")
    cmdManager.AddCommand(Command("!","help").Func(TestHelpFunc))
    cmdManager.GetCommand("help").Invoke(None)
    cmdManager.AddCommand(Command("!","test").Param(ptype = CommandParam.TYPE_INTEGER)
                                         .Param(ptype = CommandParam.TYPE_STRING)
                                         .Param(ptype = CommandParam.TYPE_BOOL)
                                         .Param(ptype = CommandParam.TYPE_FLOAT)
                                         .Param(ptype = CommandParam.TYPE_UNSIGNED)
                                         .Func(TestArgumentsFunc))
    cmdArgs = cmdParser.ParseCommand("!SomeCommand -optional2 optional2Value arg1 --paramlessOptional3 arg2 -optional1 optional1Value --paramlessOptional arg3")
    print(cmdArgs)
    testcmd = cmdManager.GetCommand("test")
    # Note: IsValidArgs method is called but not defined in original - commenting out to avoid errors
    # testcmd.IsValidArgs(cmdArgs)
    cmdManager.GetCommand("test").Invoke(cmdArgs)
