import os;
import logging;
import time;
import threading;
import lib.shared.threadcontrol as threadcontrol;
import lib.shared.remoteconsole as remoteconsole;
import io;
import queue;
import logMessage;

IsUnix      = (os.name == "posix");
IsWindows   = (os.name == "nt");

# print("ARHG %s %s" % (str(IsUnix), str(IsWindows)))

if IsUnix:
    import pty as ptym;
elif IsWindows:
    import winpty as ptym;

class IServerInterface():
    def __init__(self):
        pass;

    def Open(self) -> bool:
        return False;

    def Close(self):
        pass;
    
    def IsOpened(self) -> bool:
        return False

    def SendCommand(self, cmdstr : str, withResponse = False) -> bool:
        return True;

    def ReadResponse(self) -> str:
        return True;

    def SendRequest(self, cmdStr : str) -> bool:
        return True;

    def GetNewLines(self) -> queue.Queue:
        return None;

class AServerInterface(IServerInterface):
    def __init__(self, logger : logging.Logger):
        self._logger : logging.Logger = logger;
        self._isOpened = False;
    
    def Open(self) -> bool:
        if self._isOpened:
            self.Close();
        return True;

    def Close(self):
        if self._isOpened:
            self._isOpened = False;
    
    def IsOpened(self) -> bool:
        return self._isOpened;


class RconInterface(AServerInterface):
    def __init__(self, logger : logging.Logger, ipAddress : str, port : str, bindAddr : tuple, password : str, logPath : str, readDelay : int = 0.01):
        super().__init__(logger);
        self._logReaderLock                     = threading.Lock();
        self._logReaderThreadControl            = threadcontrol.ThreadControl();
        self._logReaderTime                     = readDelay;
        self._logReaderThread                   = threading.Thread(target=self.ParseLogThreadHandler, daemon=True,\
                                                                   args=(self._logReaderThreadControl, self._logReaderTime));
        self._logPath                           = logPath;
        self._rcon: remoteconsole.RCON          = remoteconsole.RCON( ( ipAddress, port ), bindAddr, password );
        self._queueLock : threading.Lock        = threading.Lock();
        self._linesQueueSwap : queue.Queue      = queue.Queue();
        self._workingLinesQueue : queue.Queue   = queue.Queue();
    
    def __del__(self):
        self.Close();

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
                                    self._workingLinesQueue.put(logMessage.LogMessage(line));
                                    #self._logger.debug("Woohoo : %s"%line);
                    else:
                        time.sleep(sleepTime)
                else:
                    break;
            log.close();

    def Open(self) -> bool:
        if not super().Open():
            return False;
        self._logReaderThreadControl.stop = False;
        self._logReaderThread.start();
        self._isOpened = True;
        return True;

    def Close(self):
        with self._logReaderLock:
            self._logReaderThreadControl.stop = True;
        self._logReaderThread.join();
        self._rcon.Close();
        self._linesQueueSwap.queue.clear();
        self._workingLinesQueue.queue.clear();
        super().Close();

    # Only to be called from godfinger, for now
    def GetNewLines(self) -> queue.Queue:
        with self._queueLock:
            tmp = self._workingLinesQueue;
            self._workingLinesQueue = self._linesQueueSwap;
            self._workingLinesQueue.queue.clear();
            self._linesQueueSwap = tmp;
            return self._linesQueueSwap; # should not be used until next GetNewLines;


class PtyInterface(AServerInterface):
    def __init__(self, logger : logging.Logger, inputDelay = 0.1, outputDelay = 0.1, cwd = os.getcwd(), args : list[str] = None):
        super().__init__(logger);
        self._isOpened = False;

        # read thread
        self._ptyThreadInputLock    = threading.Lock();
        self._ptyThreadInputControl = threadcontrol.ThreadControl();
        self._ptyThreadInput        = None;

        # write thread
        self._ptyThreadOutputLock      = threading.Lock();
        self._ptyThreadOutputControl   = threadcontrol.ThreadControl();
        self._ptyThreadOutput          = None;

        self._ptyInstance = None;
        self._inputDelay = inputDelay;
        self._outputDelay = outputDelay;
        self._args : list[str] = args;
        self._cwd = cwd;
    
    def __del__(self):
        self.Close();
    
    def _ThreadHandlePtyInput(self, control, frameTime):
        input : str = "";
        bsent = False;
        while True:
            timeStart = time.time();
            with self._ptyThreadInputLock:
                if control.stop:
                    break;
            try:
                if not self._ptyInstance.closed:
                        input += self._ptyInstance.read();
                        inputLines = input.splitlines();
                        if len ( inputLines ) > 0:
                            lastLine = inputLines[-1];
                            if not lastLine.endswith("\n"):
                                input = inputLines.pop(-1); # bufferize incomplete line for next frame
                            else:
                                input = "";
                            for line in inputLines:
                                if len(line) > 1:
                                    self._logger.debug("[Server] : %s"% line);
                                    # if line.startswith("Hitch warning:"):
                                    #     if not bsent:
                                    #         for i in range(100):
                                    #             self._ptyInstance.write("h%i\n"%i);
                                    #             time.sleep(self._outputDealy);
                                    #         self._ptyInstance.write("quit\n");
                                    #         time.sleep(self._outputDealy);
                                    #         self._ptyInstance.write("\x11");
                                    #         bsent = True;
                                            
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

    def _ThreadHandlePtyOutput(self, control, frameTime, outputDelay):
        while True:
            timeStart = time.time();
            with self._ptyThreadOutputLock:
                if control.stop:
                    break;
            if not self._ptyInstance.closed:
                try:                       
                    toSleep = frameTime - (time.time() - timeStart);
                    if toSleep < 0:
                        toSleep = 0;
                    time.sleep(toSleep);
                except EOFError as eofEx:
                    self._logger.debug("Server pty was closed, terminating Output thread.");
                    self._ptyInstance.close();
                    break;
            else:
                self._logger.debug("MBII PTY closed.");
                self._ptyInstance.close();
                break;
    
    def Open(self) -> bool:
        if not super().Open():
            return False;
        
        self._ptyThreadInputControl.stop    = False;
        self._ptyThreadInput                = threading.Thread(target=self._ThreadHandlePtyInput, daemon=True, args=(self._ptyThreadInputControl, self._inputDelay));
        self._ptyThreadOutputControl.stop   = False;
        self._ptyThreadOutput               = threading.Thread(target=self._ThreadHandlePtyOutput, daemon=True, args=(self._ptyThreadOutputControl, self._inputDelay, self._outputDelay));
        self._logger.debug("Arguments for child process : %s"%str(self._args));
        self._ptyInstance = ptym.PtyProcess.spawn(self._args if self._args != None else [],\
                                                cwd=self._cwd,\
                                                dimensions=(10000, 10000));
        self._logger.debug("Instance %s"%str(self._ptyInstance));
        self._ptyThreadInput.start();
        #self._ptyThreadOutput.start();
        self._isOpened = True;

    def Close(self):
        if self._isOpened:
            if self._ptyInstance != None:
                self._ptyInstance.close();
            if self._ptyThreadInput.is_alive:
                with self._ptyThreadInputLock:
                    self._ptyThreadInputControl.stop = True;
            if self._ptyThreadOutput.is_alive:
                with self._ptyThreadOutputLock:
                    self._ptyThreadOutputControl.stop = True;
            self._ptyThreadInput.join();
            self._ptyThreadOutput.join();
            self._isOpened = False;
        super().Close();
    
    def IsOpened(self) -> bool:
        return self._isOpened and not self._ptyInstance.closed;

    def SendCommand(self, cmdstr : str, withResponse = False) -> bool:
        return True;

    def ReadResponse(self) -> str:
        return True;

