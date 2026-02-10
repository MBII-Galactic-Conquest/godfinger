import socket;
import logging
import sys;
import time;
import lib.shared.timeout as  timeout;
import lib.shared.buffer as buffer;
import threading;

Log = logging.getLogger(__name__)

class RCON(object):
    def __init__(self, address, bindAddr, password):
        self._address = address;
        self._bindAddr = bindAddr;
        self._password = bytes(password, "UTF-8");
        self._sockLock = threading.Lock();
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM);
        #self._sock.setblocking(False);
        self._isOpened = False;
        self._bytesSent = 0;
        self._bytesRead = 0;
        self._inBuf = buffer.Buffer();
        self._requestTimeout = timeout.Timeout();
        self._responseParserLock = threading.Lock();
        self._responseParser = None; # a crunch method to see if the response from server is complete ( command is executed )
    
    def __del__(self):
        if self._isOpened:
            self.Close();

    def Open(self) -> bool:
        if not self.IsOpened():
            self._inBuf.Drop();
            # This try block makes no sense for UDP because we dont modify MBII for custom UDP-subprotocol
            # try:
            #     self._sock.bind((self._bindAddr, 0));
            #     self._sock.connect(self._address);
            #     self._sock.settimeout(0.001);
            self._isOpened = True;
            # except Exception:
            #     return False;
        return self._isOpened;

    def Close(self):
        if self.IsOpened():
            #self._sock.shutdown(socket.SHUT_RDWR);
            with self._sockLock:
                self._sock.close();
            self._isOpened = False;

    # Throwaway socket variant
    def _Send(self, payload : bytes):
        if self.IsOpened():
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # Socket descriptor sending/receiving rcon commands to/from the server.
            self._sock.bind((self._bindAddr, 0)) # Setting port as 0 will let the OS pick an available port for us.
            self._sock.settimeout(0.001)
            self._sock.connect(self._address)
            l = len(payload);
            sent = 0;
            while sent < l:
                sent += self._sock.send(payload[sent:l]);
            self._bytesSent += sent;
    
    # Crunches
    def _ClearInputSocket(self):
        self._Read(1024*32);

    def _Read(self, count = 1024) -> bytes:
        result = b'';
        if self.IsOpened():
            while True:
                try:
                    result += self._sock.recv(count);
                except socket.timeout:
                    break;
        self._bytesRead += len(result);
        return result;
    
    def _ReadResponse(self, count = 4096, timeout = 1) -> bool:
        bb = b'';
        if self.IsOpened():
            isFinished = False;
            self._requestTimeout.Set(timeout);
            while not isFinished:
                if not self._requestTimeout.IsSet():
                    return False;
                try:
                    bb += self._sock.recv(count);
                    if bb == b'':
                        print("Remote host closed the RCON connection.");
                        self.Close();
                        isFinished = True;
                    else:
                        if self.IsEndMessage(bb):
                            isFinished = True;
                except socket.timeout: # basically read previous recv frame and check if its completed
                    if self.IsEndMessage(bb):
                        isFinished = True;
                        break;
        self._bytesRead += len(bb);
        self._inBuf.Write(bb);
        return True;

    def _PopUnread(self) -> bytes:
        result = None;
        if self._inBuf.HasToRead():
            result = bytes(self._inBuf.Read(self._inBuf.GetEffective()));
            self._inBuf.Drop();
        return result;

    def IsEndMessage(self, bt : bytes) -> bool:
        if self._responseParser != None:
            return self._responseParser(bt);
        else: # regular \n response, valid for most commands but very big ones like map/map_restart
            if len(bt) > 0: 
                if bt[-1] == 10:
                    return True;
        return False;

    # waits for response, ensures delivery
    def Request(self, payload, responseSize = 4096, timeout = 1, responseParser = None ) -> bytes:
        if self.IsOpened():
            #print("Request with payload %s"%payload);
            result = b'';
            #startTime = time.time();
            isOk = False;
            with self._sockLock:
                if responseParser != None:
                    self._responseParser = responseParser;
                self._inBuf.Drop(); # cleanup previous calls data ( junk )
                while not isOk:
                    try:
                        self._Send(payload);
                        if not self._ReadResponse(responseSize, timeout):
                            Log.warn(f'Message with payload {str(payload)} not received after {timeout} seconds, will attempt to resend.')
                            continue;
                        else:
                            result = self._PopUnread();
                            #print("Result from request %s"%result);
                            isOk = True;
                    except Exception as ex:
                        print("Exception at Request in rcon %s" %str(ex));
                        break;
            #print("Request time %f" % (time.time() - startTime));
            if self._responseParser != None:
                self._responseParser = None;
        return result;

    def IsOpened(self)->bool:
        return self._isOpened;

    def SvSay(self, msg):
        if not type(msg) == bytes:
            msg = bytes(msg, "UTF-8")
        if len(msg) > 138: # Message is too big for "svsay".
                        # Use "say" instead.
            return self.Say(msg)
        else:
            return self.Request(b"\xff\xff\xff\xffrcon %b svsay %b" % (self._password, msg));

    def Say(self, msg):
        if not type(msg) == bytes:
            msg = bytes(msg, "UTF-8")
        return self.Request(b"\xff\xff\xff\xffrcon %b say %b" % (self._password, msg));

    def SvTell(self, clientId, msg):
        if not type(msg) == bytes:
            msg = bytes(msg, "UTF-8")
        if not type(clientId) == bytes:
            clientId = str(clientId)
            clientId = bytes(clientId, "UTF-8")
        return self.Request(b"\xff\xff\xff\xffrcon %b svtell %b %b" % (self._password, clientId, msg));

    def MbMode(self, cmd, mapToChange=None):
        """ Changes to the given MbMode (0 = Open, 1 = Semi Authentic, 2 = Full Authentic, 3 = Duel, 4 = Legends). If mapToChange is provided, also changes to that map. """
        if mapToChange == None:
            mapToChange = b""
        if not type(mapToChange) == bytes and mapToChange != b"":
            mapToChange = bytes(mapToChange, "UTF-8")
        return self.Request(b"\xff\xff\xff\xffrcon %b mbmode %i %b" % (self._password, cmd, mapToChange))
    
    def ClientMute(self, player_id : int, minutes : int = 10):
        """ Mutes the client with the given ID for the given number of minutes, or 10 minutes if no duration is given. The number of minutes must be between 1-60, inclusive. """
        if 0 < minutes <= 60:   # rcon mute must be between
            if not type(player_id) == bytes:
                player_id = bytes(str(player_id), "UTF-8")
            if not type(minutes) == bytes:
                minutes = bytes(str(minutes), "UTF-8")
            return self.Request(b"\xff\xff\xff\xffrcon %b mute %b %b" % (self._password, player_id, minutes))
        return None
  
    def ClientUnmute(self, player_id):
        return self.Request(b"\xff\xff\xff\xffrcon %b unmute %i" % (self._password, player_id));

    # untested
    def ClientBan(self, player_ip):
        if not type(player_ip) == bytes:
            player_ip = bytes(player_ip, "UTF-8")
        return self.Request(b"\xff\xff\xff\xffrcon %b addip %b" % (self._password, player_ip))
    
    # untested
    def ClientUnban(self, player_ip):
        if not type(player_ip) == bytes:
            player_ip = bytes(player_ip, "UTF-8")
        return self.Request(b"\xff\xff\xff\xffrcon %b removeip %b" % (self._password, player_ip))


    def ClientKick(self, player_id):
        return self.Request(b"\xff\xff\xff\xffrcon %b clientkick %i" % (self._password, player_id))

    def Tempban(self, player_name, rounds):
        name = bytes(player_name, "UTF-8")
        return self.Request(b"\xff\xff\xff\xffrcon %b tempban \"%b\" %i" % (self._password, name, rounds))

    def Echo(self, msg):
        msg = bytes(msg, "UTF-8")
        return self.Request(b"\xff\xff\xff\xffrcon %b echo %b" % (self._password, msg))

    def SetTeam1(self, team):
        team = team.encode()
        return self.Request(b"\xff\xff\xff\xffrcon %b g_siegeteam1 \"%b\"" % (self._password, team))

    def SetTeam2(self, team):
        team = team.encode()
        return self.Request(b"\xff\xff\xff\xffrcon %b g_siegeteam2 \"%b\"" % (self._password, team))
    
    # R20.1.01 
    def SvSound(self, soundName : str) -> bytes:     
        return self.Request(b"\xff\xff\xff\xffrcon %b snd \"%s\"" % (self._password, soundName.encode()))
    
    # R20.1.01 
    def TeamSound(self, soundName : str, teamId : int) -> bytes:
        return self.Request(b"\xff\xff\xff\xffrcon %b sndTeam %i \"%s\"" % (self._password, teamId, soundName.encode()))
    
    # R20.1.01 
    def ClientSound(self, soundName : str, clientId : int) -> bytes:
        return self.Request(b"\xff\xff\xff\xffrcon %b sndClient %i \"%s\"" % (self._password, clientId, soundName.encode()))

    def SetCvar(self, cvar, val):
        if not type(cvar) == bytes:
            cvar = bytes(cvar, "UTF-8")
        if not type(val) == bytes:
            val = bytes(val, "UTF-8")
        return self.Request(b'\xff\xff\xff\xffrcon %b %b \"%b\"' % (self._password, cvar, val))

    def GetCvar(self, cvar):
        if not type(cvar) == bytes:
            cvar = bytes(cvar, "UTF-8")
        response = self.Request(b"\xff\xff\xff\xffrcon %b %b" % (self._password, cvar))
        if response != None and len(response) > 0:
            response = response.split(b"\"")[1]
            response = response[2:-2].decode("UTF-8", errors="ignore")
        return response

    def SetVstr(self, vstr, val):
        if not type(vstr) == bytes:
            vstr = bytes(vstr, "UTF-8")
        if not type(val) == bytes:
            val = bytes(val, "UTF-8")
        return self.Request(b"\xff\xff\xff\xffrcon %b set %b \"%b\"" % (self._password, vstr, val))

    def ExecVstr(self, vstr):
        if not type(vstr) == bytes:
            vstr = bytes(vstr, "UTF-8") 
        return self.Request(b"\xff\xff\xff\xffrcon %b vstr %b" % (self._password, vstr))

    def GetTeam1(self):
        response = self.Request(b"\xff\xff\xff\xffrcon %b g_siegeteam1" % (self._password))
        response = response.decode("UTF-8", "ignore")
        if response != None and len(response) > 0:
            response = response.removeprefix("print\n\"g_siegeTeam1\" is:")
            response = response.split('"')[1][:-2]
        return response

    def GetTeam2(self):
        response = self.Request(b"\xff\xff\xff\xffrcon %b g_siegeteam2" % (self._password))
        response = response.decode("UTF-8", "ignore")
        if response != None and len(response) > 0:
            response = response.removeprefix("print\n\"g_siegeTeam2\" is:")
            response = response.split('"')[1][:-2]
        return response

    def _mapRestart(self, delay=0):
        """ (DEPRECATED, DO NOT USE) """
        return self.Request(b"\xff\xff\xff\xffrcon %b map_restart %i" % (self._password, delay))

    def _MapReloadParser(self, bb : bytes) -> bool:
        return True if bb.decode("UTF-8", "ignore").rfind("InitGame:") != -1 else False;

    def MapReload(self, mapName):
        """ USE THIS """
        if not type(mapName) == bytes:
            mapName = bytes(mapName, "UTF-8")
        response =  self.Request(b"\xff\xff\xff\xffrcon %b map %b" % (self._password, mapName), 1024*32, 120, self._MapReloadParser);
        time.sleep(5); # man, this is hard, 5 just in case, we cant be sure when it ends because there is no strict protocol
        #self._ClearInputSocket();
        return response;

    def GetCurrentMap(self):
        response = self.Request(b"\xff\xff\xff\xffrcon %b mapname" % (self._password))
        if response != None and len(response) > 0:
            response = response.removeprefix(b'\xff\xff\xff\xffprint\n^9Cvar ^7mapname = ^9"^7')
            mapName = response.removesuffix(b'^9"^7\n')
            mapName = mapName.decode("UTF-8", "ignore");
        return mapName

    def ChangeTeams(self, team1, team2, mapName):
        self.SetTeam1(team1)
        self.SetTeam2(team2)
        return self.MapReload(mapName)

    def Status(self):
        res = self.Request(b"\xff\xff\xff\xffrcon %b status notrunc" % (self._password))
        if len(res) == 0:
            return None;
        res = res.decode("UTF-8", "ignore");
        return res
    
    def DumpUser(self, user_id) -> str:
        if not type(user_id) == bytes:
            user_id = bytes(str(user_id), "UTF-8") 
        res = self.Request(b"\xff\xff\xff\xffrcon %b dumpuser %b" % (self._password, user_id));
        if res != None and len(res) > 0:
            res = res.decode("UTF-8", "ignore");
        return res;
  
    def _CvarListParser(self, bb : bytes) -> bool:
        return True if bb.decode("UTF-8", "ignore").rfind("total cvars") != -1 else False;

    def CvarList(self) -> str:
        start = time.time();
        res = self.Request(b"\xff\xff\xff\xffrcon %b cvarlist" % (self._password), responseParser=self._CvarListParser)
        if len(res) == 0:
            return None;
        res = res.decode("UTF-8", "ignore");
        #print("Cvarlist time taken %f"%(time.time() - start));
        return res
    
    def TeamSay(self, players, team, vstrStorage, msg, sleepBetweenChunks=0):
        # if not type(msg) == bytes:
        #   msg = bytes(msg, "UTF-8")
        toExecute = []
        for p in players:
            if p.GetTeamId() == team:
                toExecute.append('svtell %s %s' % (p.GetId(), msg))
        self.BatchExecute(vstrStorage, toExecute, sleepBetweenChunks)

    def BatchExecute(self, vstrStorage, cmdList, sleepBetweenChunks=0, cleanUp=True):
        """ Given a list of command strings (cmdList), executes each command at once by setting and then executing a server-side cvar """
        n = 993 - (len(vstrStorage) + 6) if cleanUp else 993  # 993 is largest vstr size from testing
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

    def SmSay(self, msg : str):
        if not type(msg) == bytes:
            msg = bytes(msg, "UTF-8")
        return self.Request(b"\xff\xff\xff\xffrcon %b smsay %s" % (self._password, msg));

    def ExecFile(self, filename : str, quiet : bool = False):
        """
        Executes a script file with the given filename.
        If the filename does not have a file extension, .cfg will be added to the end of the filename.
        The file must be in the /MBII/ directory prior to the server starting. After the file is indexed
        by the server however, the contents can be changed and changes will be reflected.
        """
        if not type(filename) == bytes:
            filename = bytes(filename, "UTF-8")
        if quiet:
            cmd = b'execq'
        else:
            cmd = b'exec'
        return self.Request(b"\xff\xff\xff\xffrcon %b %b %b" % (self._password, cmd, filename))

    def MarkTK(self, player_id : int, time : int):
        if not type(player_id) == bytes:
            player_id = bytes(str(player_id), "UTF-8")
        if not type(time) == bytes:
            time = bytes(str(time), "UTF-8")
        return self.Request(b"\xff\xff\xff\xffrcon %b marktk %b %b" % (self._password, player_id, time))

    def UnmarkTK(self, player_id : int):
        # unmarktk <client> - Removes TK mark from specified client
        if not type(player_id) == bytes:
            player_id = bytes(str(player_id), "UTF-8")
        return self.Request(b"\xff\xff\xff\xffrcon %b unmarktk %b" % (self._password, player_id))