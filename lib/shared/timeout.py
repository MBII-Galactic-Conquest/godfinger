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
            print("Timeout overflow.");
        else:
            self._overflow = False;

    def Finish(self):
        self._timeS = 0
        self._startS = 0
        self._endS = 0
        self._overflow = False
    
    def IsSet(self):
        return (self.Left() > 0);

    def TimeStart(self) -> int:
        return self._startS;

    def Left(self):
        if self._endS == 0:
            return 0;
        left = self._endS - time.time();
        if left < 0:
            left = 0;
        return left;

    def LeftDHMS(self):
        left = self.Left();
        if left > 0:
            minutes = int((left/60) % 60);
            hours = int((minutes/3600) % 60);
            days = int(hours/24);
            seconds = int(left%60)
            minutes = str(minutes).zfill(2)
            hours = str(hours).zfill(2)
            days = str(days).zfill(2)
            seconds = str(seconds).zfill(2)
                
            return f"{days}:{hours}:{minutes}:{seconds}";
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