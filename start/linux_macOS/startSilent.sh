#!/bin/bash

check_python_version() {
    REQUIRED_VERSION="3.12.0"
    INSTALLED_VERSION=$($1 -c "import sys; print('.'.join(map(str, sys.version_info[:3])))" 2>/dev/null)

    if [ -z "$INSTALLED_VERSION" ]; then
        echo "Error: Unable to check Python version with $1 (possibly missing or permission denied)"
        return 1
    fi

    echo "Installed Python version: $INSTALLED_VERSION"
    echo "Required Python version: $REQUIRED_VERSION"

    if [ "$(printf '%s\n' "$INSTALLED_VERSION" "$REQUIRED_VERSION" | sort -V | tail -n1)" = "$INSTALLED_VERSION" ]; then
        echo "Using $1 ($INSTALLED_VERSION) as it is compatible (3.12.0 or newer)"
        return 0
    else
        echo "Python version too old: $INSTALLED_VERSION (requires $REQUIRED_VERSION or newer)"
        return 1
    fi
}

if command -v python3 &>/dev/null && check_python_version "python3"; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null && check_python_version "python"; then
    PYTHON_CMD="python"
else
    echo "Error: Python 3.12+ is required but not found."
    echo "Please install Python 3 and try again."
    exit 1
fi

cd bin
chmod +x ./autostart_linux_macOS.py
$PYTHON_CMD ./autostart_linux_macOS.py
cd ../../../

chmod +x ./cleanup.sh
chmod +x ./update/update.py
chmod +x ./godfinger.py

if test -f venv/bin/activate; then
    source venv/bin/activate
    cd ./update
    $PYTHON_CMD ./update.py
    cd ../
    ./cleanup.sh
    $PYTHON_CMD ./godfinger.py -lf "./bigdata.log"
    read -p "Press Enter to continue..."
else
    echo "Virtual environment does not exist or was created improperly, please run prepare.sh in the prepare directory. Aborting."
    read -p "Press enter to exit..."
fi
