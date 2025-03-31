
def Clamp(minimum, x, maximum):
    return max(minimum, min(x, maximum))


def IsFlag(num, flag) -> bool:
    return ( num & flag ) != 0;

def IsFlags(num, flags) -> bool:
    return ( num & flags )== flags;

def SetFlag(num, flag) -> int:
    return num | flag;

def UnsetFlag(num, flag) -> int:
    return num & (~flag);