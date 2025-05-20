#!/bin/bash
# run_docker.sh - build and run godfinger docker container without .env file

IMAGE_NAME="godfinger"

echo "Building Docker image..."
docker build -f docker/Dockerfile -t $IMAGE_NAME ..

if [ $? -ne 0 ]; then
  echo "Docker build failed! Exiting."
  exit 1
fi

echo "Running Docker container..."
docker run --rm -it \
  -v ../data:/app/data \
  $IMAGE_NAME "$@"
