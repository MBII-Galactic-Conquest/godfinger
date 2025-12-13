import os
import logging
import time
import threading
import lib.shared.threadcontrol as threadcontrol
import lib.shared.remoteconsole as remoteconsole
import io
import queue
import logMessage
from file_read_backwards import FileReadBackwards
from typing import Any, Self
import re
import lib.shared.colors as colors
import lib.shared.util as util
import lib.shared.client as client
import math
import lib.shared.pswd as pswd
import lib.shared.observer as observer
import psutil

IsUnix = (os.name == "posix")
IsWindows = (os.name == "nt")

Log = logging.getLogger(__name__)

if IsUnix:
    import pty as ptym
elif IsWindows:
    import winpty as ptym

IFACE_TYPE_RCON = 0
IFACE_TYPE_PTY = 1
IFACE_TYPE_INVALID = -1

class IServerInterface():
    def __init__(self):
        pass

    def Open(self) -> bool:
        return False

    def Close(self):
        pass
    
    def IsOpened(self) -> bool:
        return False

    def SvSay(self, text : str) -> str:
        return "Not implemented"

    def Say(self, text : str) -> str:
        return "Not implemented"

    def SvTell(self, pid : int, text : str) -> str:
        return "Not implemented"

    def TeamSay(self, players, team, vstrStorage, msg):
        return "Not implemented"

    def MbMode(self, mode : int, mapToChange : str = None) -> str:
        return "Not implemented"
    
    def ClientMute(self, pid : int) -> str:
        return "Not implemented"
    
    def ClientUnmute(self, pid : int) -> str:
        return "Not implemented"
    
    def ClientBan(self, pip : str) -> str:
        return "Not implemented"
    
    def ClientUnban(self, pip : str) -> str:
        return "Not implemented"
    
    def ClientKick(self, pid : int) -> str:
        return "Not implemented"
    
    def SetCvar(self, cvarName : str, value : str) -> str:
        return "Not implemented"
    
    def GetCvar(self, cvarName : str) -> str:
        return "Not implemented"

    def SetTeam1(self, teamStr : str) -> str:
        return "Not implemented"
    
    def SetTeam2(self, teamStr : str) -> str:
        return "Not implemented"
    
    def SetVstr(self, vstrName : str, value : str) -> str:
        return "Not implemented"
    
    def ExecVstr(self, vstrName : str) -> str:
        return "Not implemented"
    
    def GetTeam1(self) -> str:
        return "Not implemented"
    
    def GetTeam2(self) -> str:
        return "Not implemented"
    
    def MapReload(self, mapname : str) -> str:
        return "Not implemented"
    
    def GetCurrentMap(self) -> str:
        return "Not implemented"
    
    def Status(self) -> str:
        return "Not implemented"
    
    def CvarList(self) -> str:
        return "Not implemented"
    
    def DumpUser(self, pid : int) -> str:
        return "Not implemented"
    
    def GetMessages(self) -> queue.Queue:
        return None

    def GetType(self) -> int:
        return IFACE_TYPE_INVALID

    def BatchExecute(self, vstrStorage, cmdList, sleepBetweenChunks=0, cleanUp=True):
        return

    def SvSound(self, soundName : str) -> str:
        return
    
    def TeamSound(self, soundName : str, teamId : int) -> str:
        return
    
    def ClientSound(self, soundName : str, clientId : int) -> str:
        return

    def SmSay(self, msg : str) -> str:
        return

    def Test(self):
        pass

    def MarkTK(self, player_id : int, time : int) -> str:
        return

class AServerInterface(IServerInterface):

    def __init__(self):
        self._queueLock = threading.Lock()
        self._messageQueueSwap = queue.Queue()
        self._workingMessageQueue = queue.Queue()
        self._isOpened = False
        self._isReady = False
        self._it = self.TypeToEnum(type(self))
    
    def Open(self) -> bool:
        if self._isOpened:
            self.Close()
        return True

    def Close(self):
        if self._isOpened:
            self._isOpened = False
        super().Close()
    
    def IsOpened(self) -> bool:
        return self._isOpened

    def TypeToEnum(self, it : type) -> int:
        if it == RconInterface:
            return IFACE_TYPE_RCON
        elif it == PtyInterface:
            return IFACE_TYPE_PTY
        else:
            return IFACE_TYPE_INVALID

    def GetType(self) -> int:
        return self._it

    def GetMessages(self) -> queue.Queue:
        with self._queueLock:
            tmp = self._workingMessageQueue
            self._workingMessageQueue = self._messageQueueSwap
            self._workingMessageQueue.queue.clear()
            self._messageQueueSwap = tmp
            return self._messageQueueSwap

    def IsReady(self) -> bool:
        return self._isReady

    def WaitUntilReady(self):
        while not self.IsReady():
            time.sleep(0.001)


class RconInterface(AServerInterface):
    def __init__(self, ipAddress : str, port : str, bindAddr : tuple, password : str, logPath : str, readDelay : int = 0.01, testRetrospect = False, procName = "mbiided.x86.exe"):
        super().__init__()
        self._logReaderLock = threading.Lock()
        self._logReaderThreadControl = threadcontrol.ThreadControl()
        self._logReaderTime = readDelay
        self._logReaderThread = threading.Thread(target=self.ParseLogThreadHandler, daemon=True,
                                                 args=(self._logReaderThreadControl, self._logReaderTime))
        self._logPath = logPath
        self._rcon = remoteconsole.RCON((ipAddress, port), bindAddr, password)
        self._testRetrospect = testRetrospect
    
        self._wdObserver = observer.Observer(self._OnWDEvent)
        self._watchdog = pswd.ProcessWatchdog(procName)
        self._watchdog.Subscribe(self._wdObserver)
    
    def __del__(self):
        self.Close()
    
    def _OnWDEvent(self, event):
        if event == pswd.WD_EVENT_PROCESS_UNAVAILABLE:
            with self._queueLock:
                self._workingMessageQueue.put(logMessage.LogMessage("wd_unavailable"))
        if event == pswd.WD_EVENT_PROCESS_EXISTING:
            with self._queueLock:
                self._workingMessageQueue.put(logMessage.LogMessage("wd_existing"))
        if event == pswd.WD_EVENT_PROCESS_STARTED:
            with self._queueLock:
                self._workingMessageQueue.put(logMessage.LogMessage("wd_started"))
        if event == pswd.WD_EVENT_PROCESS_DIED:
            with self._queueLock:
                self._workingMessageQueue.put(logMessage.LogMessage("wd_died"))
        if event == pswd.WD_EVENT_PROCESS_RESTARTED:
            with self._queueLock:
                self._workingMessageQueue.put(logMessage.LogMessage("wd_restarted"))
    
    def SvSay(self, text : str) -> str:
        if self.IsOpened():
            return self._rcon.SvSay(text)
        return None

    def Say(self, text : str) -> str:
        if self.IsOpened():
            return self._rcon.Say(text)
        return None

    def SvTell(self, pid : int, text : str) -> str:
        if self.IsOpened():
            return self._rcon.SvTell(pid, text)
        return None

    def TeamSay(self, players, team, vstrStorage, msg):
        if self.IsOpened():
            self._rcon.TeamSay(players, team, vstrStorage, msg)
    
    def BatchExecute(self, vstrStorage, cmdList, sleepBetweenChunks=0, cleanUp=True):
        if self.IsOpened():
            return self._rcon.BatchExecute(vstrStorage, cmdList, sleepBetweenChunks, cleanUp)

    def MbMode(self, mode : int, mapToChange : str = None) -> str:
        if self.IsOpened():
            return self._rcon.MbMode(mode, mapToChange)
        return None
    
    def ClientMute(self, pid : int) -> str:
        if self.IsOpened():
            return self._rcon.ClientMute(pid)
        return None
    
    def ClientUnmute(self, pid : int) -> str:
        if self.IsOpened():
            return self._rcon.ClientUnmute(pid)
        return None
    
    def ClientBan(self, pip : str) -> str:
        if self.IsOpened():
            return self._rcon.ClientBan(pip)
        return None
    
    def ClientUnban(self, pip : str) -> str:
        if self.IsOpened():
            return self._rcon.ClientUnban(pip)
        return None
    
    def ClientKick(self, pid : int) -> str:
        if self.IsOpened():
            return self._rcon.ClientKick(pid)
        return None
    
    def SetCvar(self, cvarName : str, value : str) -> str:
        if self.IsOpened():
            return self._rcon.SetCvar(cvarName, value)
        return None
    
    def GetCvar(self, cvarName : str) -> str:
        if self.IsOpened():
            return self._rcon.GetCvar(cvarName)
        return None

    def SetTeam1(self, teamStr : str) -> str:
        if self.IsOpened():
            return self._rcon.SetTeam1(teamStr)
        return None
    
    def SetTeam2(self, teamStr : str) -> str:
        if self.IsOpened():
            return self._rcon.SetTeam2(teamStr)
        return None
    
    def SetVstr(self, vstrName : str, value : str) -> str:
        if self.IsOpened():
            return self._rcon.SetVstr(vstrName, value)
        return None
    
    def ExecVstr(self, vstrName : str) -> str:
        if self.IsOpened():
            return self._rcon.ExecVstr(vstrName)
        return None
    
    def GetTeam1(self) -> str:
        if self.IsOpened():
            return self._rcon.GetTeam1()
        return None
    
    def GetTeam2(self) -> str:
        if self.IsOpened():
            return self._rcon.GetTeam2()
        return None
    
    def MapReload(self, mapname : str) -> str:
        if self.IsOpened():
            return self._rcon.MapReload(mapname)
        return None
    
    def GetCurrentMap(self) -> str:
        if self.IsOpened():
            return self._rcon.GetCurrentMap()
        return None
    
    def Status(self) -> str:
        if self.IsOpened():
            return self._rcon.Status()
        return None
    
    def CvarList(self) -> str:
        if self.IsOpened():
            return self._rcon.CvarList()
        return None
    
    def DumpUser(self, pid : int) -> str:
        if self.IsOpened():
            return self._rcon.DumpUser(pid)
        return None

    def SvSound(self, soundName : str) -> str:
        if self.IsOpened():
            return self._rcon.SvSound(soundName)
        return None
    
    def TeamSound(self, soundName : str, teamId : int) -> str:
        if self.IsOpened():
            return self._rcon.TeamSound(soundName, teamId)
        return None
    
    def ClientSound(self, soundName : str, clientId : int) -> str:
        if self.IsOpened():
            return self._rcon.ClientSound(soundName, clientId)
        return None

    def SmSay(self, msg : str) -> str:
        if self.IsOpened():
            return self._rcon.SmSay(msg)
        return None

    def ExecFile(self, filename : str) -> str:
        if self.IsOpened():
            return self._rcon.ExecFile(filename)
        return None

    def MarkTK(self, player_id : int, time : int) -> str:
        if self.IsOpened():
            return self._rcon.MarkTK(player_id, time)
        return None

    def ParseLogThreadHandler(self, control, sleepTime):
        encoding = 'utf-8' if IsUnix else 'ansi'
        with open(self._logPath, "r", encoding=encoding, errors="replace") as log:
            log.seek(0, io.SEEK_END)
            while True:
                stop = False
                with self._logReaderLock:
                    stop = control.stop
                if not stop:
                    lines = log.read()
                    linesSplit = lines.split("\n")
                    if len(linesSplit) > 0:
                        with self._queueLock:
                            for line in linesSplit:
                                if len(line) > 0:
                                    line = line[7:]
                                    self._workingMessageQueue.put(logMessage.LogMessage(line))
                    if (len(linesSplit) == 1 and linesSplit[0] == ""):
                        time.sleep(sleepTime)
                else:
                    break
            log.close()

    def Open(self) -> bool:
        if not super().Open():
            return False
        if not self._rcon.Open():
            return False
        self._watchdog.Start()

        if not os.path.exists(self._logPath):
            try:
                with open(self._logPath, "w", encoding="utf-8") as f:
                    pass
            except Exception as e:
                Log.error("Unable to create log file at path %s: %s", self._logPath, str(e))
                return False

        prestartLines = []
        logFile = None
        try:
            if IsUnix:
                logFile = FileReadBackwards(self._logPath, encoding="latin-1")
            else:
                logFile = FileReadBackwards(self._logPath, encoding="latin-1")


            for line in logFile:
                line = line[7:]
                if line.startswith("InitGame"):
                    prestartLines.append(line)
                    break
                
                lineParse = line.split()
                if len(lineParse) > 1:
                    if not self._testRetrospect:
                        if lineParse[0].startswith("SMOD"):
                            continue
                        elif lineParse[1].startswith("say"):
                            continue
                        elif lineParse[1].startswith("sayteam"):
                            continue
                
                prestartLines.append(line)
        
        except FileNotFoundError:
            Log.error("Unable to open log file at path %s to read, abort startup." % self._logPath)
            return False
    
        if len(prestartLines) > 0:
            prestartLines.reverse()
            with self._queueLock:
                for line in prestartLines:
                    self._workingMessageQueue.put(logMessage.LogMessage(line, True))
        self._logReaderThreadControl.stop = False
        self._logReaderThread.start()
        self._isOpened = True
        self._isReady = True
        return True

    def Close(self):
        if self.IsOpened():
            with self._logReaderLock:
                self._logReaderThreadControl.stop = True
            self._logReaderThread.join()
            self._rcon.Close()
            self._messageQueueSwap.queue.clear()
            self._workingMessageQueue.queue.clear()
            self._watchdog.Stop()
            super().Close()


class PtyInterface(AServerInterface):
    CMD_RESULT_FLAG_OK = 0x00000001
    CMD_RESULT_FLAG_LOG = 0x00000002
    
    class CommandProcessor():

        def __init__(self, cmd : str):
            self.cmdStr = cmd
            self._linesResponse = []
            self._responseFrameStr = None
            self._lock = threading.Lock()
            self._isReady = False
        
        def __repr__(self) -> str:
            return self.__str__()
    
        def __str__(self) -> str:
            return "Command processor, CMD %s" % self.cmdStr
        
        def _SetReady(self):
            with self._lock:
                self._isReady = True
                if len(self._linesResponse) > 0:
                    self._responseFrameStr = "\n".join(self._linesResponse)

        def IsReady(self) -> bool:
            with self._lock:
                return self._isReady
    
        def Wait(self) -> Self:
            while not self.IsReady():
                time.sleep(0.001)
            return self
        
        def GetResponse(self) -> str:
            if self.IsReady():
                return self._responseFrameStr
            else:
                return None
    
        def GetResponseLines(self) -> str:
            if self.IsReady():
                return self._linesResponse
            else:
                return None

        def Reset(self):
            with self._lock:
                self._isReady = False
                self._linesResponse.clear()
                self._responseFrameStr = None

        def ParseLine(self, line : str) -> int:
            self._linesResponse.append(line)
            return PtyInterface.CMD_RESULT_FLAG_OK
    
    class EchoProcessor(CommandProcessor):
        def __init__(self, cmd):
            super().__init__(cmd)
    
        def ParseLine(self, line):
            super().ParseLine(line)
            self._SetReady()
            return PtyInterface.CMD_RESULT_FLAG_OK

    class ReadyProcessor(CommandProcessor):
        def __init__(self, cmd):
            super().__init__(cmd)

        def ParseLine(self, line) -> int:
            self._SetReady()
            return PtyInterface.CMD_RESULT_FLAG_OK

    class QuitProcessor(CommandProcessor):
        def __init__(self, cmd):
            super().__init__(cmd)
    
        def ParseLine(self, line) -> int:
            if line.startswith("(venv)"):
                self._SetReady()
                return PtyInterface.CMD_RESULT_FLAG_OK
            return 0

    class SvSayProcessor(CommandProcessor):
        def __init__(self, cmd, message : str):
            super().__init__(cmd)
            self._message = colors.StripColorCodes(message)

        def ParseLine(self, line) -> int:
            super().ParseLine(line)
            print("%s versus %s" % (line.encode(), self._message.encode()))
            if line.startswith("broadcast:"):
                if line.find(self._message) != -1:
                    self._SetReady()
                    return PtyInterface.CMD_RESULT_FLAG_OK
            return 0

    class SayProcessor(CommandProcessor):
        def __init__(self, cmd, message : str):
            super().__init__(cmd)
            self._message = colors.StripColorCodes(message)

        def ParseLine(self, line) -> int:
            super().ParseLine(line)
            if line.startswith("broadcast:"):
                if line.find(self._message) != -1:
                    self._SetReady()
                    return PtyInterface.CMD_RESULT_FLAG_OK
            return 0

    class SvTellProcessor(CommandProcessor):
        def __init__(self, cmd, message : str):
            super().__init__(cmd)
            self._message = colors.StripColorCodes(message)

        def ParseLine(self, line) -> int:
            super().ParseLine(line)
            if line.startswith("broadcast:"):
                if line.find(self._message) != -1:
                    self._SetReady()
                    return PtyInterface.CMD_RESULT_FLAG_OK
            return 0

    class CvarlistProcessor(CommandProcessor):
        def __init__(self, cmd):
            super().__init__(cmd)

        def ParseLine(self, line) -> int:
            super().ParseLine(line)
            if line.rfind("total cvars") != -1:
                self._SetReady()
                return PtyInterface.CMD_RESULT_FLAG_OK
            return 0

    class StatusProcessor(CommandProcessor):
        def __init__(self, cmd):
            super().__init__(cmd)

        def ParseLine(self, line) -> int:
            super().ParseLine(line)
            if line == "":
                self._SetReady()
                return PtyInterface.CMD_RESULT_FLAG_OK
            return 0

    class GetCvarProcessor(CommandProcessor):
        def __init__(self, cmd):
            super().__init__(cmd)
    
        def ParseLine(self, line) -> int:
            super().ParseLine(line)
            if line.find("Cvar %s" % self.cmdStr) != -1:
                self._SetReady()
                return PtyInterface.CMD_RESULT_FLAG_OK
            return 0

        def GetResponse(self):
            lines = super().GetResponseLines()
            curLine = lines[1]
            response = curLine.split("\"")[1]
            return response
            
    class SetCvarProcessor(CommandProcessor):
        def __init__(self, cmd):
            super().__init__(cmd)
    
        def ParseLine(self, line) -> int:
            super().ParseLine(line)
            if line == self.cmdStr:
                self._SetReady()
                return PtyInterface.CMD_RESULT_FLAG_OK
            return 0

    class DumpuserProcessor(CommandProcessor):
        def __init__(self, cmd):
            self._linesRead = 0
            super().__init__(cmd)
    
        def ParseLine(self, line) -> int:
            print("Parsing line %s" % line)
            if self._linesRead < 3:
                super().ParseLine(line)
                self._linesRead += 1
                return 0
            splitted = line.split()
            l = len(splitted)
            if l < 2:
                self._SetReady()
                return PtyInterface.CMD_RESULT_FLAG_OK | PtyInterface.CMD_RESULT_FLAG_LOG
            first = splitted[0]
            if first.find(":") != -1:
                self._SetReady()
                return PtyInterface.CMD_RESULT_FLAG_OK | PtyInterface.CMD_RESULT_FLAG_LOG
            super().ParseLine(line)
            return 0

    class SetVstrProcessor(CommandProcessor):
        def __init__(self, cmd):
            super().__init__(cmd)
    
        def ParseLine(self, line) -> int:
            super().ParseLine(line)
            self._SetReady()
            return PtyInterface.CMD_RESULT_FLAG_OK

    class ExecVstrProcessor(CommandProcessor):
        def __init__(self, cmd):
            super().__init__(cmd)
    
        def ParseLine(self, line):
            super().ParseLine(line)
            self._SetReady()
            return PtyInterface.CMD_RESULT_FLAG_OK

    class MapReloadProcessor(CommandProcessor):
        def __init__(self, cmd):
            super().__init__(cmd)
    
        def ParseLine(self, line) -> int:
            super().ParseLine(line)
            self._SetReady()
            return PtyInterface.CMD_RESULT_FLAG_OK

    MODE_INPUT = 0
    MODE_COMMAND = 1

    def __init__(self, inputDelay = 0.001, cwd = os.getcwd(), args = None):
        super().__init__()

        self._ptyThreadInputLock = threading.Lock()
        self._ptyThreadInputControl = threadcontrol.ThreadControl()
        self._ptyThreadInput = None

        self._ptyInstance = None
        self._inputDelay = inputDelay
        self._args = args
        self._cwd = cwd
        self._commandProcQLock = threading.Lock()
        self._commandProcQueue = queue.Queue()
        self._currentCommandProc = None
        self._mode = PtyInterface.MODE_INPUT
    
        self._re_ansi_escape = re.compile(r'''
            \x1B  # ESC
            (?:   # 7-bit C1 Fe (except CSI)
                [@-Z\\-_]
            |     # or [ for CSI, followed by a control sequence
                \[
                [0-?]*  # Parameter bytes
                [ -/]*  # Intermediate bytes
                [@-~]   # Final byte
            )
        ''', re.VERBOSE)
    
    def __del__(self):
        self.Close()
    
    def _TruncateString(self, text : str) -> list:
        tl = len(text)
        parts = math.floor(tl / 63)
        moda = tl % 63
        result = []
        if parts > 0:
            for i in range(parts):
                result.append(text[i * 63:(i + 1) * 63])
            if moda > 0:
                result.append(text[parts * 63:])
        else:
            result.append(text)
        return result

    def SvSay(self, text : str) -> str:
        if self.IsOpened():
            strs = self._TruncateString(text)
            result = ""
            for i in range(len(strs)):
                cmdStr = "svsay %s" % strs[i]
                proc = PtyInterface.SvSayProcessor(colors.StripColorCodes(cmdStr), strs[i])
                result += self.ExecuteCommand(cmdStr, proc)
            return result
        return None

    def Say(self, text : str) -> str:
        if self.IsOpened():
            strs = self._TruncateString(text)
            result = ""
            for i in range(len(strs)):
                cmdStr = "say %s" % strs[i]
                proc = PtyInterface.SayProcessor(colors.StripColorCodes(cmdStr), strs[i])
                result += self.ExecuteCommand(cmdStr, proc)
            return result
        return None

    def SvTell(self, text : str, pid : int) -> str:
        if self.IsOpened():
            strs = self._TruncateString(text)
            result = ""
            for i in range(len(strs)):
                cmdStr = "svtell %i %s" % (pid, strs[i])
                proc = PtyInterface.SayProcessor(colors.StripColorCodes(cmdStr), strs[i])
                result += self.ExecuteCommand(cmdStr, proc)
            return result
        return None

    def TeamSay(self, players, team, vstrStorage, msg):
        if self.IsOpened():
            toExecute = []
            for p in players:
                if p.GetTeamId() == team:
                    toExecute.append('svtell %s %s' % (p.GetId(), msg))
            self.BatchExecute(vstrStorage, toExecute, 0.01)

    def BatchExecute(self, vstrStorage, cmdList, sleepBetweenChunks=0, cleanUp=True):
        n = 993 - (len(vstrStorage) + 6) if cleanUp else 993
        payload = ''
        for cmd in cmdList:
            cmd += ';'
            if len(payload) + len(cmd) < n:
                payload += cmd
            else:
                if cleanUp:
                    payload += f'unset {vstrStorage}'
            self.SetVstr(vstrStorage, payload)
            self.ExecVstr(vstrStorage)
            payload = cmd
            if sleepBetweenChunks > 0:
                time.sleep(sleepBetweenChunks)
        if len(payload) > 0:
            if cleanUp:
                payload += f'unset {vstrStorage}'
            self.SetVstr(vstrStorage, payload)
            self.ExecVstr(vstrStorage)

    def MbMode(self, mode : int) -> str:
        if self.IsOpened():
            cmdStr = "mbmode %s" % (mode)
            proc = PtyInterface.SetCvarProcessor(cmdStr)
            return self.ExecuteCommand(cmdStr, proc)
        return None
    
    def ClientMute(self, pid : int) -> str:
        if self.IsOpened():
            cmdStr = "mute %i" % (pid)
            proc = PtyInterface.EchoProcessor(cmdStr)
            return self.ExecuteCommand(cmdStr, proc)
        return None
    
    def ClientUnmute(self, pid : int) -> str:
        if self.IsOpened():
            cmdStr = "unmute %i" % (pid)
            proc = PtyInterface.EchoProcessor(cmdStr)
            return self.ExecuteCommand(cmdStr, proc)
        return None
    
    def ClientBan(self, pip : str) -> str:
        if self.IsOpened():
            cmdStr = "addip %s" % (pip)
            proc = PtyInterface.EchoProcessor(cmdStr)
            return self.ExecuteCommand(cmdStr, proc)
        return None
    
    def ClientUnban(self, pip : str) -> str:
        if self.IsOpened():
            cmdStr = "removeip %s" % (pip)
            proc = PtyInterface.EchoProcessor(cmdStr)
            return self.ExecuteCommand(cmdStr, proc)
        return None
    
    def ClientKick(self, pid : int) -> str:
        if self.IsOpened():
            cmdStr = "clientkick %i" % (pid)
            proc = PtyInterface.EchoProcessor(cmdStr)
            return self.ExecuteCommand(cmdStr, proc)
        return None
    
    def SetCvar(self, cvarName : str, value : str) -> str:
        if self.IsOpened():
            cmdStr = "%s %s" % (cvarName, value)
            proc = PtyInterface.SetCvarProcessor(cmdStr)
            return self.ExecuteCommand(cmdStr, proc)
        return None
    
    def GetCvar(self, cvarName : str) -> str:
        if self.IsOpened():
            cmdStr = "%s" % cvarName
            proc = PtyInterface.GetCvarProcessor(cmdStr)
            return self.ExecuteCommand(cmdStr, proc)
        return None

    def SetTeam1(self, teamStr : str) -> str:
        if self.IsOpened():
            return self.SetCvar("g_siegeteam1", teamStr)
        return None
    
    def SetTeam2(self, teamStr : str) -> str:
        if self.IsOpened():
            return self.SetCvar("g_siegeteam2", teamStr)
        return None
    
    def SetVstr(self, vstrName : str, value : str) -> str:
        if self.IsOpened():
            return self.SetCvar(vstrName, value)
        return None
    
    def ExecVstr(self, vstrName : str) -> str:
        if self.IsOpened():
            return self.GetCvar(vstrName)
        return None
    
    def GetTeam1(self) -> str:
        if self.IsOpened():
            return self.GetCvar("g_siegeteam1")
        return None
    
    def GetTeam2(self) -> str:
        if self.IsOpened():
            return self.GetCvar("g_siegeteam2")
        return None
    
    def MapReload(self, mapname : str) -> str:
        if self.IsOpened():
            cmdStr = "map %s" % (mapname)
            proc = PtyInterface.MapReloadProcessor(cmdStr)
            return self.ExecuteCommand(cmdStr, proc)
        return None
    
    def GetCurrentMap(self) -> str:
        if self.IsOpened():
            return self.GetCvar("mapname")
        return None
    
    def Status(self) -> str:
        if self.IsOpened():
            cmdStr = "status"
            proc = PtyInterface.StatusProcessor(cmdStr)
            return self.ExecuteCommand(cmdStr, proc)
        return None
    
    def CvarList(self) -> str:
        if self.IsOpened():
            cmdStr = "cvarlist"
            proc = PtyInterface.CvarlistProcessor(cmdStr)
            return self.ExecuteCommand(cmdStr, proc)
        return None
    
    def DumpUser(self, pid : int) -> str:
        if self.IsOpened():
            cmdStr = "dumpuser %s" % (pid)
            proc = PtyInterface.DumpuserProcessor(cmdStr)
            return self.ExecuteCommand(cmdStr, proc)
        return None

    def _Quit(self) -> str:
        if self.IsOpened():
            cmd = "quit"
            proc = PtyInterface.QuitProcessor(cmd)
            self._EnqueueCommandProc(proc)
            self._ptyInstance.write(cmd + "\n")
            proc.Wait()
            self._ptyInstance.write("\n")
            return ""
        return None

    def ExecuteCommand(self, cmdStr : str, cmdProc) -> str:
        self._EnqueueCommandProc(cmdProc)
        self._ptyInstance.write(cmdStr + "\n")
        return cmdProc.Wait().GetResponse()

    def _ThreadHandlePtyInput(self, control, frameTime):
        input = ""
        MIN_SLEEP_S = 0.005 # Force a 5ms yield time to prevent 100% CPU spin
        while True:
            timeStart = time.time()
            with self._ptyThreadInputLock:
                if control.stop:
                    break
            try:
                if not self._ptyInstance.closed:
                    input += self._ptyInstance.read()

                    if self._currentCommandProc == None:
                        if not self._commandProcQueue.empty():
                            self._currentCommandProc = self._commandProcQueue.get()

                    inputLines = input.splitlines()
                    if len(inputLines) > 0:
                        lastLine = inputLines[-1]
                        if not lastLine.endswith("\n"):
                            input = inputLines.pop(-1)
                        else:
                            input = ""
                        for line in inputLines:
                            line = self._re_ansi_escape.sub("", line)
                            if self._mode == PtyInterface.MODE_COMMAND:
                                pr = self._currentCommandProc.ParseLine(line)
                                if util.IsFlag(pr, PtyInterface.CMD_RESULT_FLAG_OK):
                                    self._currentCommandProc = None
                                    self._mode = PtyInterface.MODE_INPUT
                                    if util.IsFlag(pr, PtyInterface.CMD_RESULT_FLAG_LOG):
                                        Log.info("[Server] : \"%s\"" % line)
                                        self._workingMessageQueue.put(logMessage.LogMessage(line))
                            else:
                                Log.info("[Server] : \"%s\"" % line)
                                if self._currentCommandProc != None:
                                    if line == self._currentCommandProc.cmdStr:
                                        pr = self._currentCommandProc.ParseLine(line)
                                        if util.IsFlag(pr, PtyInterface.CMD_RESULT_FLAG_OK):
                                            self._currentCommandProc = None
                                        else:
                                            self._mode = PtyInterface.MODE_COMMAND
                                        continue
                                self._workingMessageQueue.put(logMessage.LogMessage(line))

                    toSleep = frameTime - (time.time() - timeStart)

                    if IsUnix:
                        # FIX: Enforce minimum sleep
                        if toSleep < MIN_SLEEP_S:
                            time.sleep(MIN_SLEEP_S)
                        else:
                            time.sleep(toSleep)
                    else:
                        if toSleep < 0:
                            toSleep = 0
                        time.sleep(toSleep)
                else:
                    Log.info("MBII PTY closed.")
                    self._ptyInstance.close()
                    break
            except EOFError as eofEx:
                Log.info("Server pty was closed, terminating Input thread.")
                self._ptyInstance.close()
                break
            except Exception as ex:
                Log.info("What the fuck %s" % str(ex))
                self._ptyInstance.close()
                break
    
    def _EnqueueCommandProc(self, cmdProc):
        with self._commandProcQLock:
            self._commandProcQueue.put(cmdProc)
    
    def Open(self) -> bool:
        if not super().Open():
            return False
        
        self._ptyThreadInputControl.stop = False
        self._ptyThreadInput = threading.Thread(target=self._ThreadHandlePtyInput, daemon=True, args=(self._ptyThreadInputControl, self._inputDelay))

        self._ptyInstance = ptym.PtyProcess.spawn(self._args if self._args != None else [],
                                                cwd=self._cwd,
                                                dimensions=(1024, 1024))
        initProc = PtyInterface.ReadyProcessor("------- Game Initialization -------")
        self._EnqueueCommandProc(initProc)
        self._ptyThreadInput.start()
        self._isOpened = True
        initProc.Wait()
        self._isReady = True
        return self.IsOpened()

    def Close(self):
        if self.IsOpened():
            if IsUnix:
                with self._logReaderLock:
                    self._logReaderThreadControl.stop = True

                # FIX: Add a timeout (e.g., 2.0s) to prevent indefinite blocking during shutdown
                self._logReaderThread.join(timeout=2.0)

                self._rcon.Close()
                self._messageQueueSwap.queue.clear()
                self._workingMessageQueue.queue.clear()
                self._watchdog.Stop()
            else:
                if self._ptyInstance != None:
                    self._Quit()
                    time.sleep(1)
                    self._ptyInstance.close()
                if self._ptyThreadInput.is_alive:
                    with self._ptyThreadInputLock:
                        self._ptyThreadInputControl.stop = True
                self._ptyThreadInput.join()
                self._isOpened = False
        super().Close()

    def IsOpened(self) -> bool:
        return self._isOpened and not self._ptyInstance.closed

    def Test(self):
        super().Test()
        start = time.time()
        response = self.Say("Testing")
        Log.debug("Testing svsay response %s, time taken %f" % (response, time.time() - start))
        
        start = time.time()
        response = self.SvSay("Testing")
        Log.debug("Testing say response %s, time taken %f" % (response, time.time() - start))

        start = time.time()
        response = self.CvarList()
        Log.debug("Testing cvarlist response %s, time taken %f" % (response, time.time() - start))

        start = time.time()
        response = self.Status()
        Log.debug("Testing status response %s, time taken %f" % (response, time.time() - start))
