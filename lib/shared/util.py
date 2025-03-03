import traceback;
import inspect;

def Clamp(minimum, x, maximum):
    return max(minimum, min(x, maximum))


def FullTracebackString(tb_frame) -> str:
    result = "";
    if tb_frame != None:
        return result;



def TestNest(argumentvar1, argumentvar2):
    localVar = 1234;
    localString = "bunghole";
    raise Exception("FUCK");

def Test():
    print("\nAYYY CARUMBA");
    try:
        TestNest(1337, "Fucking Idiot");
    except Exception as sex:
        print(str(inspect.trace()[-1][0].f_locals));


if __name__ == "__main__":
    Test();