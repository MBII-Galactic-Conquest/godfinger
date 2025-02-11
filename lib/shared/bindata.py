# wrapper class for bytes so they have name
class Bindata():
    def __init__(self, name, bytes):
        self.name = name;
        self.bytes = bytes;