import lib.shared.client as client;
import threading;

class ClientManager():
    def __init__(self):
        self._clients = [];
        self._lock = threading.Lock();
    
    def Reset(self):
        with self._lock:
            self._clients.clear();
    
    def GetClientCount(self) -> int:
        with self._lock:
            return len(self._clients);

    def GetAllClients(self) -> list[client.Client]:
        with self._lock:
            return self._clients.copy();

    def GetClientById(self, id) -> client.Client:
        with self._lock:
            for client in self._clients:
                if client.GetId() == id:
                    return client;
        return None;

    def GetClientByName(self, name : str )-> client.Client:
        with self._lock:
            for client in self._clients:
                if client.GetName() == name:
                    return client;
        return None;

    def AddClient(self, client : client.Client):
        with self._lock:
            if client not in self._clients:
                self._clients.append(client);

    def RemoveClient(self, client : client.Client):
        with self._lock:
            if client in self._clients:
                self._clients.remove(client);
    
    def RemoveClientById(self, id : int):
        client = self.GetClientById(id);
        if client != None:
            self.RemoveClient(client);

    def UpdateClient(self, id : int, data : str):
        cl = self.GetClientById();
        if cl != None:
            with self._lock:
                cl.Update(data);