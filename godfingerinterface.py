import os;
import logging;
import time;
import threading;
import lib.shared.threadcontrol as threadcontrol;
import lib.shared.remoteconsole as remoteconsole;
import io;
import queue;
import logMessage;
from file_read_backwards import FileReadBackwards
from typing import Any, Self;
import re;
import lib.shared.colors as colors;

IsUnix      = (os.name == "posix");
IsWindows   = (os.name == "nt");

# print("ARHG %s %s" % (str(IsUnix), str(IsWindows)))

if IsUnix:
    import pty as ptym;
elif IsWindows:
    import winpty as ptym;

IFACE_TYPE_RCON         = 0;
IFACE_TYPE_PTY          = 1;
IFACE_TYPE_INVALID      = -1;

class IServerInterface():
    def __init__(self):
        pass;

    def Open(self) -> bool:
        return False;

    def Close(self):
        pass;
    
    def IsOpened(self) -> bool:
        return False

    # str are server response, can be None or ""
    def SendCommand(self, args : list[str], force : bool = False) -> str:
        return "True";


    def GetMessages(self) -> queue.Queue:
        return None;

    def GetType(self) -> int:
        return IFACE_TYPE_INVALID;

class AServerInterface(IServerInterface):

    def __init__(self, logger : logging.Logger):
        self._logger                : logging.Logger = logger;
        self._queueLock             : threading.Lock        = threading.Lock();
        self._messageQueueSwap      : queue.Queue           = queue.Queue();
        self._workingMessageQueue   : queue.Queue           = queue.Queue();
        self._isOpened = False;
        self._isReady = False;
        self._it = self.TypeToEnum(type(self));
    
    def Open(self) -> bool:
        if self._isOpened:
            self.Close();
        return True;

    def Close(self):
        if self._isOpened:
            self._isOpened = False;
    
    def IsOpened(self) -> bool:
        return self._isOpened;

    def TypeToEnum(self, it : type) -> int:
        if it == RconInterface:
            return IFACE_TYPE_RCON;
        elif it == PtyInterface:
            return IFACE_TYPE_PTY;
        else:
            return IFACE_TYPE_INVALID;

    def GetType(self) -> int:
        return self._it;

    # Only to be called from godfinger, for now
    # I call this, THE REVOLVER
    def GetMessages(self) -> queue.Queue:
        with self._queueLock:
            tmp = self._workingMessageQueue;
            self._workingMessageQueue = self._messageQueueSwap;
            self._workingMessageQueue.queue.clear();
            self._messageQueueSwap = tmp;
            return self._messageQueueSwap; # should not be used until next GetNewLines;

    # TODO
    def IsReady(self) -> bool:
        return self._isReady;

    def WaitUntilReady(self):
        while not self.IsReady():
            time.sleep(0.001); # 1ms is enough, dont thread on me


class RconInterface(AServerInterface):
    def __init__(self, logger : logging.Logger, ipAddress : str, port : str, bindAddr : tuple, password : str, logPath : str, readDelay : int = 0.01, testRetrospect = False):
        super().__init__(logger);
        self._logReaderLock                     = threading.Lock();
        self._logReaderThreadControl            = threadcontrol.ThreadControl();
        self._logReaderTime                     = readDelay;
        self._logReaderThread                   = threading.Thread(target=self.ParseLogThreadHandler, daemon=True,\
                                                                   args=(self._logReaderThreadControl, self._logReaderTime));
        self._logPath                           = logPath;
        self._rcon: remoteconsole.RCON          = remoteconsole.RCON( ( ipAddress, port ), bindAddr, password );
        self._testRetrospect                    = testRetrospect;
    
    def __del__(self):
        self.Close();
    
    def SendCommand(self, args : list[str], force : bool = False) -> str:
        self._logger.debug("Sending rcon command %s"%str(args));
        if len (args) > 0:
            if self.IsOpened():
                cmd = args[0];
                if self._rcon.IsOpened():
                        if cmd == "svsay":
                            return self._rcon.SvSay(args[1]);
                        elif cmd == "say":
                            return self._rcon.Say(args[1]);
                        elif cmd == "svtell":
                            return self._rcon.SvTell(args[1],args[2]);
                        elif cmd == "mbmode":
                            return self._rcon.MbMode(args[1]);
                        elif cmd == "clientmute":
                            return self._rcon.ClientMute(args[1]);
                        elif cmd == "clientunmute":
                            return self._rcon.ClientUnmute(args[1]);
                        elif cmd == "clientban":
                            return self._rcon.ClientBan(args[1]);
                        elif cmd == "clientunban":
                            return self._rcon.ClientUnban(args[1]);
                        elif cmd == "clientkick":
                            return self._rcon.ClientKick(args[1]);
                        elif cmd == "setteam1":
                            return self._rcon.SetTeam1(args[1]);
                        elif cmd == "setteam2":
                            return self._rcon.SetTeam2(args[1]);
                        elif cmd == "setcvar":
                            return self._rcon.SetCvar(args[1], args[2]);
                        elif cmd == "getcvar":
                            return self._rcon.GetCvar(args[1]);
                        elif cmd == "setvstr":
                            return self._rcon.SetVstr(args[1], args[2]);
                        elif cmd == "execvstr":
                            return self._rcon.ExecVstr(args[1]);
                        elif cmd == "getteam1":
                            return self._rcon.GetTeam1();
                        elif cmd == "getteam2":
                            return self._rcon.GetTeam2();
                        elif cmd == "mapreload":
                            return self._rcon.MapReload(args[1]);
                        elif cmd == "getcurrentmap":
                            return self._rcon.GetCurrentMap();
                        elif cmd == "changeteams":
                            return self._rcon.ChangeTeams(args[1], args[2], args[3]);
                        elif cmd == "status":
                            return self._rcon.Status();
                        elif cmd == "cvarlist":
                            return self._rcon.CvarList();
                        elif cmd == "dumpuser":
                            return self._rcon.DumpUser();
                        else:
                            self._logger.error("Unknown command for rcon interface %s"%cmd);
        return "";

    def ParseLogThreadHandler(self, control, sleepTime):
        with open(self._logPath, "r") as log:
            log.seek(0, io.SEEK_END)
            while True:
                stop = False;
                with self._logReaderLock:
                    stop = control.stop;
                if not stop:
                    # Parse server log line
                    lines = log.readlines();
                    if len(lines) > 0:
                        with self._queueLock:
                            for line in lines:
                                if len(line) > 0:
                                    line = line[7:];
                                    self._workingMessageQueue.put(logMessage.LogMessage(line));
                    else:
                        time.sleep(sleepTime)
                else:
                    break;
            log.close();

    def Open(self) -> bool:
        if not super().Open():
            return False;
        # FileReadBackwards package doesnt "support" ansi encoding in stock, change it yourself
        prestartLines = [];
        logFile = None;
        try:
            if IsUnix:
                logFile = FileReadBackwards(self._logPath, encoding = "utf-8");
            else:
                logFile = FileReadBackwards(self._logPath, encoding="ansi");
            
            for line in logFile:
                line = line[7:];
                if line.startswith("InitGame"):
                    prestartLines.append(line);
                    break;
                
                # filter out player retrospect player messages.
                lineParse = line.split()
                l = len(lineParse);
                if l > 1:
                    if not self._testRetrospect:
                        if lineParse[0].startswith("SMOD"):
                            continue
                        elif lineParse[1].startswith("say"):
                            continue;
                        elif lineParse[1].startswith("sayteam"):
                            continue;
                
                prestartLines.append(line);
        
        except FileNotFoundError:
            self._logger.error("Unable to open log file at path %s to read, abort startup." % self._logPath);
            return False;
    
        if len(prestartLines) > 0:
            prestartLines.reverse();
            with self._queueLock:
                for i in range(len(prestartLines)):
                    self._workingMessageQueue.put(logMessage.LogMessage(prestartLines[i], True));
        self._rcon.Open();
        self._logReaderThreadControl.stop = False;
        self._logReaderThread.start();
        self._isOpened = True;
        self._isReady = True;
        return True;

    def Close(self):
        if self.IsOpened():
            with self._logReaderLock:
                self._logReaderThreadControl.stop = True;
            self._logReaderThread.join();
            self._rcon.Close();
            self._messageQueueSwap.queue.clear();
            self._workingMessageQueue.queue.clear();
            super().Close();



class PtyInterface(AServerInterface):

    class CommandProcessor():
        def __init__(self, cmd : str):
            self.cmdStr = cmd;
            self._linesResponse : list[str] = [];
            self._responseFrameStr : str = None;
            self._lock = threading.Lock();
            self._isReady = False;
        
        def _SetReady(self):
            with self._lock:
                self._isReady = True;
                if len ( self._linesResponse ) > 1:
                    self._responseFrameStr = "\n".join(self._linesResponse[1:]); # skip the first line since its always the echoed command

        def IsReady(self) -> bool:
            with self._lock:
                return self._isReady;
    
        def Wait(self) -> Self:
            while not self.IsReady():
                time.sleep(0.001);
            return self;
        
        def GetResponse(self) -> str:
            if self.IsReady():
                return self._responseFrameStr;
            else:
                return None; # wait
    
        def GetResponseLines(self) -> str:
            if self.IsReady():
                return self._linesResponse;
            else:
                return None; # wait

        def Reset(self):
            with self._lock:
                self._isReady = False;
                self._linesResponse.clear();
                self._responseFrameStr = None;

        # return True if finished processing
        # return False if not finished, used to keep reading from log instead of global feed
        # First line is always cmdStr, should be
        def ParseLine(self, line : str) -> bool:
            self._linesResponse.append(line);
            return True;
    
    # Technical
    class ReadyProcessor(CommandProcessor):
        def __init__(self, cmd, ptyInst):
            super().__init__(cmd)
            self._ptyInst = ptyInst;

        def ParseLine(self, line) -> bool:
            #print("\"%s\""%line);
            self._SetReady();
            return True;

    class QuitProcessor(CommandProcessor):
        def __init__(self, cmd):
            super().__init__(cmd);
    
        def ParseLine(self, line) -> bool:
            #print("ASDF %s"%line);
            if line.startswith("(venv)"):
                self._isReady = True;
                return True;
            return False;

    # Commands
    class SvSayProcessor(CommandProcessor):
        def __init__(self, cmd, message : str):
            super().__init__(cmd);
            self._message = colors.stripColorCodes(message);

        def ParseLine(self, line) -> bool:
            super().ParseLine(line);
            print("%s versus %s"%(line.encode(), self._message.encode()));
            if line.startswith("broadcast:"):
                if line.find(self._message) != -1:
                    self._SetReady();
                    return True;

    class SayProcessor(CommandProcessor):
        def __init__(self, cmd, message : str):
            super().__init__(cmd);
            self._message = colors.stripColorCodes(message);

        def ParseLine(self, line) -> bool:
            super().ParseLine(line);
            print("%s versus %s"%(line.encode(), self._message.encode()));
            if line.startswith("broadcast:"):
                if line.find(self._message) != -1:
                    self._SetReady();
                    return True;

    class SvTellProcessor(CommandProcessor):
        def __init__(self, cmd, message : str):
            super().__init__(cmd);
            self._message = colors.stripColorCodes(message);

        def ParseLine(self, line) -> bool:
            super().ParseLine(line);
            print("%s versus %s"%(line.encode(), self._message.encode()));
            if line.startswith("broadcast:"):
                if line.find(self._message) != -1:
                    self._SetReady();
                    return True;

    class CvarlistProcessor(CommandProcessor):
        def __init__(self, cmd):
            super().__init__(cmd);

        def ParseLine(self, line) -> bool:
            super().ParseLine(line);
            #print("%s versus %s"%(line.encode(), self._message.encode()));
            if line.rfind("total cvars") != -1:
                self._SetReady();
                return True;

    class StatusProcessor(CommandProcessor):
        def __init__(self, cmd):
            super().__init__(cmd);

        def ParseLine(self, line) -> bool:
            super().ParseLine(line);
            # b'Cvar g_campaignRotationFile = "campaignRotation"
            print("Status processing line %s"%(line.encode()));
            if line == "":
                self._SetReady();
                return True;

    class GetCvarProcessor(CommandProcessor):
        def __init__(self, cmd):
            super().__init__(cmd);
    
        def ParseLine(self, line) -> bool:
            super().ParseLine(line);
            if line.find("Cvar %s"%self.cmdStr) != -1:
                self._SetReady();
                return True;

        def GetResponse(self):
            lines =  super().GetResponseLines();
            curLine = lines[1];
            response = curLine.split("\"")[1];
            return response;
            
    class SetCvarProcessor(CommandProcessor):
        def __init__(self, cmd):
            super().__init__(cmd);
    
        def ParseLine(self, line) -> bool:
            super().ParseLine(line);
            if line == self.cmdStr:
                self._SetReady();
                return True;
            
    
    MODE_INPUT   = 0;
    MODE_COMMAND = 1;


    def __init__(self, logger : logging.Logger, inputDelay = 0.001, cwd = os.getcwd(), args : list[str] = None):
        super().__init__(logger);

        # read thread
        self._ptyThreadInputLock    = threading.Lock();
        self._ptyThreadInputControl = threadcontrol.ThreadControl();
        self._ptyThreadInput        = None;

        # write thread
        # self._ptyThreadOutputLock      = threading.Lock();
        # self._ptyThreadOutputControl   = threadcontrol.ThreadControl();
        # self._ptyThreadOutput          = None;

        self._ptyInstance = None;
        self._inputDelay = inputDelay;
        # self._outputDelay = outputDelay;
        self._args : list[str] = args;
        self._cwd = cwd;
        self._commandProcQLock = threading.Lock();
        self._commandProcQueue : queue.Queue = queue.Queue();
        self._currentCommandProc : PtyInterface.CommandProcessor = None;
        self._mode = PtyInterface.MODE_INPUT; # 0 for regular read, 1 for command feed
    
        # 7-bit C1 ANSI sequences
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
        ''', re.VERBOSE);
    
    def __del__(self):
        self.Close();
    
    # def _ReadyListener(self, line : str) -> bool:
    #     if line.find("Common Initialization Complete") != -1:
    #         self._isReady = True;
    #         self._logger.info("pty listener is ready, server is up.");
    #         return True;

    def _ThreadHandlePtyInput(self, control, frameTime):
        input : str = "";
        bsent = False;
        while True:
            timeStart = time.time();
            with self._ptyThreadInputLock:
                if control.stop:
                    break;
                if self._currentCommandProc == None:
                    if self._commandProcQueue.not_empty:
                        self._currentCommandProc = self._commandProcQueue.get();
            try:
                if not self._ptyInstance.closed:
                        input += self._ptyInstance.read();
                        #self._logger.debug("Read %i from stream -> %s : %s"%(len(input), input, input.encode()));
                        inputLines = input.splitlines();
                        if len ( inputLines ) > 0:
                            lastLine = inputLines[-1];
                            if not lastLine.endswith("\n"):
                                input = inputLines.pop(-1); # bufferize incomplete line for next frame
                            else:
                                input = "";
                            for line in inputLines:
                                #print("line %s"%line.encode());
                                line = self._re_ansi_escape.sub("", line);
                                #if len(line) > 1:
                                # Command mode
                                if self._mode == PtyInterface.MODE_COMMAND:
                                    if self._currentCommandProc.ParseLine(line):
                                        self._currentCommandProc = None;
                                        self._mode = PtyInterface.MODE_INPUT;
                                        self._logger.debug("Setting mode to MODE_INPUT");
                                # Regular read mode
                                else: 
                                    self._logger.debug("[Server] : \"%s\""% line);
                                    if self._currentCommandProc != None:
                                        #print("Fuck ! \"%s\" : \"%s\""%(line, self._currentCommandProc.cmdStr));
                                        if line == self._currentCommandProc.cmdStr:
                                            if self._currentCommandProc.ParseLine(line):
                                                self._currentCommandProc = None;
                                            else:
                                                self._logger.debug("Setting mode to MODE_COMMAND");
                                                self._mode = PtyInterface.MODE_COMMAND;
                                            continue;
                                        # else:
                                        #     self._logger.debug("asrgs %s :"%(line.encode()));
                                    self._workingMessageQueue.put(logMessage.LogMessage(line));
                                # if line.startswith("Hitch warning:"):
                                #     if not bsent:
                                #         for i in range(100):
                                #             self._ptyInstance.write("h%i\n"%i);
                                #             time.sleep(self._outputDealy);
                                #         self._ptyInstance.write("quit\n");
                                #         time.sleep(self._outputDealy);
                                #         self._ptyInstance.write("\x11");
                                #         bsent = True;
                        #self._logger.debug("Time taken %f"%(time.time() - timeStart));
                        toSleep = frameTime - (time.time() - timeStart);
                        if toSleep < 0:
                            toSleep = 0;
                        time.sleep(toSleep);
                else:
                    self._logger.debug("MBII PTY closed.");
                    self._ptyInstance.close();
                    break;
            except EOFError as eofEx:
                self._logger.debug("Server pty was closed, terminating Input thread.");
                self._ptyInstance.close();
                break;
            except Exception as ex:
                self._logger.debug("What the fuck %s" % str(ex));
                self._ptyInstance.close();
                break;
    
    def _EnqueueCommandProc(self, cmdProc):
        with self._commandProcQLock:
            self._commandProcQueue.put(cmdProc);

    # def _ThreadHandlePtyOutput(self, control, frameTime):
    #     while True:
    #         timeStart = time.time();
    #         with self._ptyThreadOutputLock:
    #             if control.stop:
    #                 break;
    #         if not self._ptyInstance.closed:
    #             try:                       
    #                 toSleep = frameTime - (time.time() - timeStart);
    #                 if toSleep < 0:
    #                     toSleep = 0;
    #                 time.sleep(toSleep);
    #             except EOFError as eofEx:
    #                 self._logger.debug("Server pty was closed, terminating Output thread.");
    #                 self._ptyInstance.close();
    #                 break;
    #         else:
    #             self._logger.debug("MBII PTY closed.");
    #             self._ptyInstance.close();
    #             break;
    
    def Open(self) -> bool:
        if not super().Open():
            return False;
        
        self._ptyThreadInputControl.stop    = False;
        self._ptyThreadInput                = threading.Thread(target=self._ThreadHandlePtyInput, daemon=True, args=(self._ptyThreadInputControl, self._inputDelay));
        # self._ptyThreadOutputControl.stop   = False;
        # self._ptyThreadOutput               = threading.Thread(target=self._ThreadHandlePtyOutput, daemon=True, args=(self._ptyThreadOutputControl, self._inputDelay, self._outputDelay));
        self._logger.debug("Arguments for child process : %s"%str(self._args));
        self._ptyInstance = ptym.PtyProcess.spawn(self._args if self._args != None else [],\
                                                cwd=self._cwd,\
                                                dimensions=(1024, 1024));
        self._logger.debug("Instance %s"%str(self._ptyInstance));
        initProc = PtyInterface.ReadyProcessor("------- Game Initialization -------", self);
        self._EnqueueCommandProc(initProc);
        self._ptyThreadInput.start();
        self._isOpened = True;
        initProc.Wait();
        # self._ptyThreadOutput.start();
        self._isReady = True;
        return self.IsOpened();

    def Close(self):
        if self.IsOpened():
            if self._ptyInstance != None:
                self.SendCommand(["quit"]);
                time.sleep(1); # UGH
                self._ptyInstance.close();
            if self._ptyThreadInput.is_alive:
                with self._ptyThreadInputLock:
                    self._ptyThreadInputControl.stop = True;
            # if self._ptyThreadOutput.is_alive:
            #     with self._ptyThreadOutputLock:
            #         self._ptyThreadOutputControl.stop = True;
            self._ptyThreadInput.join();
            # self._ptyThreadOutput.join();
            self._isOpened = False;
        super().Close();
    
    def IsOpened(self) -> bool:
        return self._isOpened and not self._ptyInstance.closed;

    def SendCommand(self, args : list[str], force : bool = False) -> str:
        self._logger.debug("Sending pty command %s"%str(args));
        if len (args) > 0:
            if self.IsOpened():
                cmd = args[0];
                if force:
                    cmd = "".join(args);
                else:
                    proc = None;
                    if cmd == "svsay":
                        cmdStr = "svsay %s"%args[1];
                        #self._logger.debug(cmdStr);
                        #self._logger.debug("WHAT THE FUCK %s" % self._re_ansi_escape.sub("", cmdStr));
                        proc = PtyInterface.SvSayProcessor(colors.stripColorCodes(cmdStr),args[1]);
                        self._EnqueueCommandProc(proc);
                        self._logger.debug("aargh %s"%cmdStr);
                        self._ptyInstance.write(cmdStr+"\n")
                        return proc.Wait().GetResponse();
                    elif cmd == "say":
                        cmdStr = "say %s"%args[1];
                        proc = PtyInterface.SayProcessor(colors.stripColorCodes(cmdStr),args[1]);
                        self._EnqueueCommandProc(proc);
                        self._ptyInstance.write(cmdStr+"\n")
                        return proc.Wait().GetResponse();
                    elif cmd == "svtell":
                        cmdStr = "svtell %i %s"%(args[1], args[2]);
                        proc = PtyInterface.SvTellProcessor(colors.stripColorCodes(cmdStr),args[1]);
                        self._EnqueueCommandProc(proc);
                        self._ptyInstance.write(cmdStr+"\n")
                        return proc.Wait().GetResponse();
                    elif cmd == "mbmode":
                        return self._rcon.MbMode(args[1]);
                    elif cmd == "clientmute":
                        return self._rcon.ClientMute(args[1]);
                    elif cmd == "clientunmute":
                        return self._rcon.ClientUnmute(args[1]);
                    elif cmd == "clientban":
                        return self._rcon.ClientBan(args[1]);
                    elif cmd == "clientunban":
                        return self._rcon.ClientUnban(args[1]);
                    elif cmd == "clientkick":
                        return self._rcon.ClientKick(args[1]);
                    elif cmd == "setteam1":
                        cmdStr = "setteam1 %s"%(args[1]);
                        proc = PtyInterface.SetCvarProcessor(cmdStr);
                        self._EnqueueCommandProc(proc);
                        self._ptyInstance.write(cmdStr+"\n")
                        return proc.Wait().GetResponse();
                    elif cmd == "setteam2":
                        cmdStr = "setteam2 %s"%(args[1]);
                        proc = PtyInterface.SetCvarProcessor(cmdStr);
                        self._EnqueueCommandProc(proc);
                        self._ptyInstance.write(cmdStr+"\n")
                        return proc.Wait().GetResponse();
                    elif cmd == "setcvar":
                        cmdStr = "%s %s"%(args[1], args[2]);
                        proc = PtyInterface.SetCvarProcessor(cmdStr);
                        self._EnqueueCommandProc(proc);
                        self._ptyInstance.write(cmdStr+"\n")
                        return proc.Wait().GetResponse();
                    elif cmd == "getcvar":
                        cmdStr = "%s"%args[1];
                        proc = PtyInterface.GetCvarProcessor(cmdStr);
                        self._EnqueueCommandProc(proc);
                        self._ptyInstance.write(cmdStr+"\n")
                        response = proc.Wait().GetResponse();
                        return response;
                    elif cmd == "setvstr":
                        return self._rcon.SetVstr(args[1], args[2]);
                    elif cmd == "execvstr":
                        return self._rcon.ExecVstr(args[1]);
                    elif cmd == "getteam1":
                        cmdStr = "g_siegeteam1";
                        proc = PtyInterface.GetCvarProcessor(cmdStr);
                        self._EnqueueCommandProc(proc);
                        self._ptyInstance.write(cmdStr+"\n")
                        response = proc.Wait().GetResponse();
                        return response;
                    elif cmd == "getteam2":
                        cmdStr = "g_siegeteam1";
                        proc = PtyInterface.GetCvarProcessor(cmdStr);
                        self._EnqueueCommandProc(proc);
                        self._ptyInstance.write(cmdStr+"\n")
                        response = proc.Wait().GetResponse();
                        return response;
                    elif cmd == "mapreload":
                        return self._rcon.MapReload(args[1]);
                    elif cmd == "getcurrentmap":
                        return self._rcon.GetCurrentMap();
                    elif cmd == "changeteams":
                        return self._rcon.ChangeTeams(args[1], args[2], args[3]);
                    elif cmd == "status":
                        cmdStr = "status";
                        proc = PtyInterface.StatusProcessor(cmdStr);
                        self._EnqueueCommandProc(proc);
                        self._ptyInstance.write(cmdStr+"\n")
                        return proc.Wait().GetResponse();
                    elif cmd == "cvarlist":
                        start = time.time();
                        cmdStr = "cvarlist";
                        proc = PtyInterface.CvarlistProcessor(cmdStr);
                        self._EnqueueCommandProc(proc);
                        self._ptyInstance.write(cmdStr+"\n")
                        response = proc.Wait().GetResponse();
                        print("Cvarlist time taken %f"%(time.time() - start));
                        return response;
                    elif cmd == "dumpuser":
                        return self._rcon.DumpUser();
                    elif cmd == "quit":
                        proc = PtyInterface.QuitProcessor(cmd);
                        self._EnqueueCommandProc(proc);
                        self._ptyInstance.write(cmd+"\n");
                        proc.Wait();
                        #time.sleep(1.5);
                        self._ptyInstance.write("\n");
                        return "";
                    else:
                        self._logger.error("Unknown command for rcon interface %s"%cmd);
        return "";



            

    # def SendCommand(self, cmd : str) -> str:
    #     if self.IsOpened():
    #         cmd = cmd.lower();
    #         parsedCmd = cmd.split();
    #         if self._rcon.IsOpened():
    #             if len(parsedCmd) > 1:
    #                 cmd = parsedCmd[0];
    #                 args = parsedCmd[1:];
    #                 if cmd == "svs":
    #                     return self._rcon.SvSay(args[1]);
    #                 elif cmd == "s":
    #                     return self._rcon.Say(args[1]);
    #                 elif cmd == "svt":
    #                     return self._rcon.SvTell(args[1],args[2]);
    #                 elif cmd == "mbm":
    #                     return self._rcon.MbMode(args[1]);
    #                 elif cmd == "cm":
    #                     return self._rcon.ClientMute(args[1]);
    #                 elif cmd == "cum":
    #                     return self._rcon.ClientUnmute(args[1]);
    #                 elif cmd == "cb":
    #                     return self._rcon.ClientBan(args[1]);
    #                 elif cmd == "cub":
    #                     return self._rcon.ClientUnban(args[1]);
    #                 elif cmd == "ck":
    #                     return self._rcon.ClientKick(args[1]);
    #                 elif cmd == "st1":
    #                     return self._rcon.SetTeam1(args[1]);
    #                 elif cmd == "st2":
    #                     return self._rcon.SetTeam2(args[1]);
    #                 elif cmd == "scvar":
    #                     return self._rcon.SetCvar(args[1], args[2]);
    #                 elif cmd == "gcvar":
    #                     return self._rcon.GetCvar(args[1]);
    #                 elif cmd == "svstr":
    #                     return self._rcon.SetVstr(args[1], args[2]);
    #                 elif cmd == "evstr":
    #                     return self._rcon.ExecVstr(args[1]);
    #                 elif cmd == "gt1":
    #                     return self._rcon.GetTeam1(args[1]);
    #                 elif cmd == "g2":
    #                     return self._rcon.GetTeam2(args[1]);
    #                 elif cmd == "mr":
    #                     return self._rcon.MapReload(args[1]);
    #                 elif cmd == "gcm":
    #                     return self._rcon.GetCurrentMap();
    #                 elif cmd == "ct":
    #                     return self._rcon.ChangeTeams(args[1], args[2], args[3]);
    #                 elif cmd == "status":
    #                     return self._rcon.Status();
    #                 elif cmd == "cvl":
    #                     return self._rcon.CvarList();
    #                 elif cmd == "du":
    #                     return self._rcon.DumpUser();
    #         return "";

