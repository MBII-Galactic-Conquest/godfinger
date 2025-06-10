

import psutil;
import threading;
import lib.shared.threadcontrol as threadcontrol;
import lib.shared.timeout as timeout;
import time;
import lib.shared.observer as observer;


WD_EVENT_PROCESS_UNAVAILABLE = -1; # not existing on start of watch
WD_EVENT_PROCESS_EXISTING    = 0; # raised only once upon start of watch
WD_EVENT_PROCESS_DIED        = 1; # was alive before but now dead
WD_EVENT_PROCESS_STARTED     = 2; # died but then gone back online
WD_EVENT_PROCESS_RESTARTED   = 3; # was alive, died, then started

class ProcessWatchdog:
    def __init__(self, processName : int, frameTime = 0.1):
        self._observable = observer.Observable();
        self._processName = processName;
        self._frameTime = frameTime;
        self._isRunning = False;
        self._watcherControl = threadcontrol.ThreadControl();
        self._controlLock    = threading.Lock();
        self._watchThread    = threading.Thread(target=self._WatchThreadHandler, daemon=True, args=(self._frameTime,));

    def _WatchThreadHandler(self, frameTime):
        frameTimeout    = timeout.Timeout();
        isAlive         = False;
        hasDied         = False;

        pid = self._GetPid();
        if pid != -1:
            isAlive = True;
            self._observable.Raise(WD_EVENT_PROCESS_EXISTING);
        else:
            self._observable.Raise(WD_EVENT_PROCESS_UNAVAILABLE);
        
        while True:
            with self._controlLock:
                if self._watcherControl.stop:
                    break;
            frameTimeout.Set(frameTime);

            if pid != -1:
                if psutil.pid_exists(pid):
                    if not isAlive:
                        self._observable.Raise(WD_EVENT_PROCESS_STARTED);
                        isAlive = True;
                    if hasDied:
                        self._observable.Raise(WD_EVENT_PROCESS_RESTARTED);
                        hasDied = False;    
                else:
                    if isAlive:
                        self._observable.Raise(WD_EVENT_PROCESS_DIED);
                        isAlive = False;
                        hasDied  = True;
                    pid = -1;
            else:
                if isAlive:
                    isAlive = False;
                    hasDied = True;
                pid = self._GetPid();
            
            time.sleep(frameTimeout.Left());

    def _GetPid(self) -> int:
        pid = -1;
        for proc in psutil.process_iter():
            if proc.name() == self._processName:
                pid = proc.pid;
        return pid;

    def Start(self):
        if not self._isRunning:
            self._watchThread.start();
            self._isRunning = True;

    def Stop(self):
        if self._isRunning:
            with self._controlLock:
                self._watcherControl.stop = True;
            self._isRunning = False;
            self._watchThread.join();

    # LE FACADEE
    def Subscribe(self, observer : observer.Observer):
        observer.Subscribe(self._observable);

    def Unsubscribe(self, observer : observer.Observer):
        self._observable.Unsubscribe(observer);