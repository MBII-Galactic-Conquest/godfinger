import file_read_backwards
import os

def main():
    fullpath = file_read_backwards.__file__
    targetPath = os.path.dirname(fullpath)
    targetPath = os.path.join(targetPath, "file_read_backwards.py")
    print(targetPath)
    
    try:
        with open(targetPath, "r") as f:
            contents = f.read()

        needToFix = contents.find("supported_encodings = [\"utf-8\", \"ascii\", \"ansi\", \"latin-1\"]")
        
        if needToFix == -1:
            print("Fixing backwards reader.")
            posBegin = contents.find("supported_encodings")
            posEnd = contents.find("]")
            
            if posEnd != -1 and posBegin != -1:
                posEnd += 1
                prolog = contents[:posBegin]
                epilog = contents[posEnd:]
                modified = prolog + "supported_encodings = [\"utf-8\", \"ascii\", \"ansi\", \"latin-1\"]" + epilog
                
                with open(targetPath, "w") as f:
                    f.write(modified)
                print("Done")
        else:
            print("Not needed to fix backwards reader.")
    
    except Exception as e:
        print(f"Error occurred: {e}")
    
    # Wait for user input with the option to press Enter or type 'continue' to proceed
    while True:
        user_input = input("\nPress Enter or type 'continue' to proceed... ").strip().lower()
        if user_input == "" or user_input == "continue":
            break  # Exit the loop and proceed with the program
        else:
            print("Invalid input. Please press Enter or type 'continue' to proceed.")

main()
