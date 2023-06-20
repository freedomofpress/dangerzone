#!/bin/sh

set -e

TAG=dangerzone.rocks/dangerzone:latest

echo "Building container image"
docker build dangerzone/ -f Dockerfile --tag $TAG

echo "Saving and compressing container image"
docker save $TAG | gzip > share/container.tar.gz

echo "Looking up the image id"
docker images -q --filter=reference=$TAG > share/image-id.txt
