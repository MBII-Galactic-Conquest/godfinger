

class ExportInstance():
    def __init__(self, name : str, pointer : any, isFunc : bool = True ):
        self.name = name;
        self.pointer = pointer;
        self.isfunc = isFunc;

class ExportTable():
    def __init__(self):
        self.instances = list[ExportInstance]();

    def Add(self, name : str, pointer : any, isFunc : bool = True):
        self.instances.append(ExportInstance(name, pointer, isFunc));

    def Get(self, name) -> ExportInstance:
        for inst in self.instances:
            if inst.name == name:
                return inst;
        return None;

    def copy(self):
        rslt = ExportTable();
        rslt.instances = self.instances.copy();
        return rslt;