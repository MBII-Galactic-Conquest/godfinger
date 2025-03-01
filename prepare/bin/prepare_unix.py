import file_read_backwards
import os
import sys
import site

def main():
    # Check if OS is Linux or macOS
    if sys.platform.startswith('linux') or sys.platform.startswith('darwin'):
        # Get the site-packages directory for Linux/macOS
        site_packages = site.getsitepackages()
        print(f"Site Packages Directories: {site_packages}")
        
        # Assuming the package is installed in the site-packages directory
        for package_path in site_packages:
            targetPath = os.path.join(package_path, "file_read_backwards.py")
            if os.path.isfile(targetPath):
                print(f"Found file_read_backwards.py at: {targetPath}")
                break
        else:
            print("file_read_backwards.py not found in site-packages.")

    else:
        # Handle other OS types (Windows, etc.)
        fullpath = file_read_backwards.__file__
        targetPath = os.path.dirname(fullpath)
        targetPath = os.path.join(targetPath, "file_read_backwards.py")
        print(f"Found file_read_backwards.py at: {targetPath}")
    
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
