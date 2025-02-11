import lib.shared.client as client;

class Player():
    def __init__(self, cl : client.Client):
        self._client = cl;

    def GetClient(self) -> client.Client:
        return self._client;

    def GetId(self) -> int:
        return self._client.GetId();

    def GetName(self) -> str:
        return self._client.GetName();

    def GetAddress(self) -> str:
        return self._client.GetAddress();

    def GetInfo(self) -> dict[str, str]:
        return self._client.GetInfo();

    def GetTeamId(self) -> int:
        return self._client.GetTeamId();

    def __repr__(self):
        s = f"{self.GetName()} (ID : {str(self.GetId())})"
        return s