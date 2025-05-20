#!/bin/bash

IMAGE_NAME="godfinger"

echo "Building Docker image..."
docker build -f docker/Dockerfile -t $IMAGE_NAME ..

if [ $? -ne 0 ]; then
  echo "Docker build failed! Exiting."
  exit 1
fi

# Ensure Jedi Academy & Moviebattles II is installed in RWD/../dockerize
echo "Checking for Jedi Academy installation..."
docker run --rm -it \
  -v ../../dockerize:/app/jediacademy \
  $IMAGE_NAME "$@"

# Now migrate the script extension system
echo "Running Docker container..."
docker run --rm -it \
  -v ..:/app/jediacademy/gamedata/godfinger \
  $IMAGE_NAME "$@"