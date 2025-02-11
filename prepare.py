import file_read_backwards;
import os;

def main():
    fullpath = file_read_backwards.__file__;
    targetPath = os.path.dirname(fullpath);
    targetPath = os.path.join(targetPath, "file_read_backwards.py");
    print(targetPath);
    try:
        f = open(targetPath, "r");
        contents = f.read();
        f.close();
        needToFix = contents.find("supported_encodings = [\"utf-8\", \"ascii\", \"ansi\", \"latin-1\"]");
        if needToFix == -1:
            print("Fixing backwards reader.");
            posBegin = contents.find("supported_encodings");
            posEnd = contents.find("]");
            if posEnd != -1 and posBegin != 1:
                posEnd += 1;
                prolog = contents[:posBegin];
                epilog = contents[posEnd:];
                modified = prolog + "supported_encodings = [\"utf-8\", \"ascii\", \"ansi\", \"latin-1\"]" + epilog;
                f = open(targetPath, "w");
                f.write(modified);  
                f.close();
                print("Done");
        else:
            print("Not needed to fix backwards reader.");
    except Exception:
        print("OOf");


main();