from socket import (socket, AF_INET, SOCK_STREAM, SOCK_DGRAM, SHUT_RDWR, gethostbyname_ex,
                    gaierror, timeout as socketTimeout, error as socketError)
from time import time, sleep
import lib.shared.timeout as timeout;
import time;

def TruncateMessage(message) -> list[str]:
  l = len(message);
  result = list[str]();
  if l >= 128:
    chunks = int(l/128) + 1;
    #print("Length is " + str(l) + " chunks count : " + str(chunks));
    toRead = 0;
    read = 0;
    for chunk in range(chunks):
      toRead = (chunk + 1) * 128;
      readLeft = l - read;
      if readLeft <= 128:
        # last chunk, less or equal to 128 length
        toRead = l;
      result.append(message[chunk*128:toRead]);
      read = toRead;
  else:
    result.append(message);
  return result;

class Rcon(object):
  """Send commands to the server via rcon. Wrapper class."""
  def __init__(self, address, bindaddr, rcon_pwd, frameTime = 0.02, rate = 5):
    self.address = address
    self.bindaddr = bindaddr
    self.rcon_pwd = bytes(rcon_pwd, "UTF-8")
    self._frameTime = frameTime;
    self._rate = rate;
    self._counter = 0;
    self._timeout = timeout.Timeout();
    self._lastCheckTick = time.time();

  def __del__(self):
    pass

  def _TimeoutWait(self):
    while ( self._timeout.IsSet() ):
      pass;

  def _Send(self, payload, buffer_size=1024, waitForResponse=True): # This method shouldn't be used outside the scope of this object's
                                              # wrappers.
    curTick = time.time();
    if curTick - self._lastCheckTick >= self._frameTime:
      self._counter = 0;
      self._lastCheckTick = curTick;
    elif self._counter >= self._rate:
      self._timeout.Set(self._frameTime);
      self._TimeoutWait();
      self._counter = 0;
    sock = socket(AF_INET, SOCK_DGRAM) # Socket descriptor sending/receiving rcon commands to/from the server.
    sock.bind((self.bindaddr, 0)) # Setting port as 0 will let the OS pick an available port for us.
    sock.settimeout(1)
    sock.connect(self.address)
    send = sock.send
    recv = sock.recv
    while(True): # Make sure an infinite loop is placed until
                 # the command is successfully received.
      try:
        send(payload)
        if waitForResponse:
          a = b''
          while(True):
            try:
              a += recv(buffer_size)
            except socketTimeout:
              break
        break

      except socketTimeout:
        continue

      except socketError:
        print("socket error")
        break

    sock.shutdown(SHUT_RDWR)
    sock.close()
    self._counter += 1;
    if waitForResponse:
      return a
    else:
      return None

  def say(self, msg):
    if not type(msg) == bytes:
      msg = bytes(msg, "UTF-8")
    return self._Send(b"\xff\xff\xff\xffrcon %b say %b" % (self.rcon_pwd, msg),
               2048, waitForResponse=False)

  def svsay(self, msg):
    if not type(msg) == bytes:
      msg = bytes(msg, "UTF-8")
    if len(msg) > 138: # Message is too big for "svsay".
                       # Use "say" instead.
      return self.say(msg)

    else:
      return self._Send(b"\xff\xff\xff\xffrcon %b svsay %b" % (self.rcon_pwd, msg), waitForResponse=False)
    
  # requires custom MBII fork to work
  def teamsayvstr(self, players, team, vstrStorage, vstrMsg, sleepBetweenChunks=0):
    # if not type(msg) == bytes:
    #   msg = bytes(msg, "UTF-8")
    toExecute = []
    for p in players:
      if p.GetTeamId() == team:
        toExecute.append('svtell %s $%s' % (p.GetId(), vstrMsg))
    self.batchExecute(vstrStorage, toExecute, sleepBetweenChunks)

  def teamsay(self, players, team, vstrStorage, msg, sleepBetweenChunks=0):
    # if not type(msg) == bytes:
    #   msg = bytes(msg, "UTF-8")
    toExecute = []
    for p in players:
      if p.GetTeamId() == team:
        toExecute.append('svtell %s %s' % (p.GetId(), msg))
    self.batchExecute(vstrStorage, toExecute, sleepBetweenChunks)

  def batchExecute(self, vstrStorage, cmdList, sleepBetweenChunks=0, cleanUp=True):
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
        self.setVstr(vstrStorage, payload)
        self.execVstr(vstrStorage)
        payload = cmd
        if sleepBetweenChunks > 0:
          sleep(sleepBetweenChunks)
    if len(payload) > 0:
      if cleanUp:
          payload += f'unset {vstrStorage}'
      self.setVstr(vstrStorage, payload)
      self.execVstr(vstrStorage)
      

  def svtell(self, client, msg):
    if not type(msg) == bytes:
      msg = bytes(msg, "UTF-8")
    if not type(client) == bytes:
      client = str(client)
      client = bytes(client, "UTF-8")
    return self._Send(b"\xff\xff\xff\xffrcon %b svtell %b %b" % (self.rcon_pwd, client, msg), waitForResponse=False)

  def mbmode(self, cmd):
    return self._Send(b"\xff\xff\xff\xffrcon %b mbmode %i" % (self.rcon_pwd, cmd))

  def clientkick(self, player_id):
    return self._Send(b"\xff\xff\xff\xffrcon %b clientkick %i" % (self.rcon_pwd, player_id))
  
  # untested
  def clientban(self, player_ip):
    return self._Send(b"\xff\xff\xff\xffrcon %b addip %s" % (self.rcon_pwd, player_ip))
  
  # untested
  def clientunban(self, player_ip):
    return self._Send(b"\xff\xff\xff\xffrcon %b removeip %s" % (self.rcon_pwd, player_ip))
  
  def echo(self, msg):
    msg = bytes(msg, "UTF-8")
    return self._Send(b"\xff\xff\xff\xffrcon %b echo %b" % (self.rcon_pwd, msg))

  def setTeam1(self, team):
    team = team.encode()
    return self._Send(b"\xff\xff\xff\xffrcon %b g_siegeteam1 \"%b\"" % (self.rcon_pwd, team))
  
  def setTeam2(self, team):
    team = team.encode()
    return self._Send(b"\xff\xff\xff\xffrcon %b g_siegeteam2 \"%b\"" % (self.rcon_pwd, team))

  def setCvar(self, cvar, val):
    if not type(cvar) == bytes:
      cvar = bytes(cvar, "UTF-8")
    if not type(val) == bytes:
      val = bytes(val, "UTF-8")
    return self._Send(b'\xff\xff\xff\xffrcon %b %b \"%b\"' % (self.rcon_pwd, cvar, val), waitForResponse=False)

  def getCvar(self, cvar):
    if not type(cvar) == bytes:
      cvar = bytes(cvar, "UTF-8")
    response = self._Send(b"\xff\xff\xff\xffrcon %b %b" % (self.rcon_pwd, cvar))
    if response != None and len(response) > 0:
      if len(response.split(b"\"")) > 1:
        response = response.split(b"\"")[1]
        response = response[2:-2].decode("UTF-8", errors="ignore")
      else:
        response = b'error'
    return response

  def setVstr(self, vstr, val):
    if not type(vstr) == bytes:
      vstr = bytes(vstr, "UTF-8")
    if not type(val) == bytes:
      val = bytes(val, "UTF-8")
    return self._Send(b"\xff\xff\xff\xffrcon %b set %b \"%b\"" % (self.rcon_pwd, vstr, val), waitForResponse=False)
  
  def execVstr(self, vstr):
    if not type(vstr) == bytes:
      vstr = bytes(vstr, "UTF-8") 
    return self._Send(b"\xff\xff\xff\xffrcon %b vstr %b" % (self.rcon_pwd, vstr), waitForResponse=False)

  def getTeam1(self):
    repeats = 10;
    while repeats > 0:
      response = self._Send(b"\xff\xff\xff\xffrcon %b g_siegeteam1" % (self.rcon_pwd));
      response = response.decode("UTF-8", "ignore")
      if response == "":
        repeats -= 1;
        sleep(0.1);
        continue;
      response = response.removeprefix("print\n\"g_siegeTeam1\" is:")
      response = response.split('"')[1][:-2].strip();
      return response
    return None;

  def getTeam2(self):
    repeats = 10;
    while repeats > 0:
      response = self._Send(b"\xff\xff\xff\xffrcon %b g_siegeteam2" % (self.rcon_pwd))
      response = response.decode("UTF-8", "ignore")
      if response == "":
        repeats -= 1;
        sleep(0.1);
        continue;
      response = response.removeprefix("print\n\"g_siegeTeam2\" is:")
      response = response.split('"')[1][:-2].strip();
      return response
    return None;
  
  def _mapRestart(self, delay=0):
    """ (DEPRECATED, DO NOT USE) """
    return self._Send(b"\xff\xff\xff\xffrcon %b map_restart %i" % (self.rcon_pwd, delay))
  
  def mapReload(self, mapName):
    """ USE THIS """
    currMap = bytes(mapName, "UTF-8")
    #self._Send(b"\xff\xff\xff\xffrcon %b mbmode 4" % (self.rcon_pwd))
    return self._Send(b"\xff\xff\xff\xffrcon %b map %b" % (self.rcon_pwd, currMap))

  def getCurrentMap(self):
    response = self._Send(b"\xff\xff\xff\xffrcon %b mapname" % (self.rcon_pwd))
    response = response.removeprefix(b'\xff\xff\xff\xffprint\n^9Cvar ^7mapname = ^9"^7')
    mapName = response.removesuffix(b'^9"^7\n')
    return mapName

  def changeTeams(self, team1, team2, mapName):
    self.setTeam1(team1)
    self.setTeam2(team2)
    return self.mapReload(mapName)

  def status(self):
    res = self._Send(b"\xff\xff\xff\xffrcon %b status notrunc" % (self.rcon_pwd))
    if len(res) == 0:
      return None;
    return res

  def dumpuser(self, id):
    if not type(id) == bytes:
      id = bytes(str(id), "UTF-8") 
    res = self._Send(b"\xff\xff\xff\xffrcon %b dumpuser %b" % (self.rcon_pwd, id))
    return res