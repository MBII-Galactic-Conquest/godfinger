import time

class Timeout:
    def __init__(self):
        self._startS = 0;
        self._endS = 0;
        self._timeS = 0;
        self._overflow = False;

    def Set(self, seconds):
        self._startS = time.time();
        self._timeS = seconds;
        self._endS = self._startS + self._timeS;
        if self._endS < self._startS:
            self._overflow = True;
            print("Timeout overflow error.");
        else:
            self._overflow = False;
    
    def IsSet(self):
        return (self.Left() > 0);

    def TimeStart(self) -> int:
        return self._startS;

    def Left(self):
        return (self._endS - time.time());

    def LeftDHMS(self):
        left = self.Left();
        if left > 0:
            minutes = (left/60) % 60;
            hours = (minutes/3600) % 60;
            days = (hours/24);
            return "%d:%d:%d:%d"%(days, hours, minutes, (left%60));
        else:
            return "00:00:00";

    # Thread blocking await
    def Wait(self):
        while(self.IsSet()):
            pass;
    
    # Thread blocking await
    def WaitFor(self, seconds):
        self.Set(seconds);
        self.Wait();