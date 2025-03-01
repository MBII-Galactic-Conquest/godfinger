#!/bin/bash
cd ../../
check_python_version() {
    REQUIRED_VERSION="3.12.0"
    INSTALLED_VERSION=$($1 -c "import sys; print('.'.join(map(str, sys.version_info[:3])))")

    if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$INSTALLED_VERSION" | sort -V | head -n1)" = "$REQUIRED_VERSION" ]; then
        echo "Using $1 ($INSTALLED_VERSION)"
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

if test -f venv/Scripts/activate; then
    source venv/Scripts/activate
    cd ./update
    $PYTHON_CMD	./update.py
    cd ../
    ./cleanup.sh
    $PYTHON_CMD ./godfinger.py --debug -lf "./bigdata.log"
    read -p "Press Enter to continue..."
else
    echo on
    echo Virtual environment does not exist or was created improperly, please run prepare.bat in prepare dir, aborting.
    echo "Press enter to exit..."
    read input
fi


