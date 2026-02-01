#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Get the godfinger root directory (parent of docker/)
GODFINGER_DIR="$(dirname "$SCRIPT_DIR")"
# Get the parent of godfinger (where dockerize should be)
PARENT_DIR="$(dirname "$GODFINGER_DIR")"

IMAGE_NAME="godfinger"

echo "Building Docker image..."
docker build -f "$SCRIPT_DIR/Dockerfile" -t $IMAGE_NAME "$GODFINGER_DIR"

if [ $? -ne 0 ]; then
  echo "Docker build failed! Exiting."
  exit 1
fi

# Ensure Jedi Academy & Moviebattles II is installed in $PARENT_DIR/dockerize

echo "Running Docker container..."
docker run --rm -it \
    -v "$PARENT_DIR/dockerize:/app/jediacademy" \
    -v "$GODFINGER_DIR:/app/jediacademy/gamedata/godfinger" \
    -v "$PARENT_DIR/configstore_godfinger:/app/jediacademy/gamedata/godfinger/data" \
    $IMAGE_NAME "$@"