


class API():
    def __init__(self):
        self.GetClientCount     = None;
        self.GetClientById      = None;
        self.GetClientByName    = None;
        self.GetAllClients      = None;
        self.GetCurrentMap      = None;
        self.GetServerVar       = None;
        self.SetServerVar       = None;
        self.CreateDatabase     = None;
        self.AddDatabase        = None;
        self.GetDatabase        = None;
        self.GetPlugin          = None; # plugName, returns plugin object ptr, None if not found