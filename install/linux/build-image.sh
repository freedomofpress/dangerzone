#!/bin/sh

set -e

TAG=dangerzone.rocks/dangerzone:latest

echo "Building container image"
podman build dangerzone/ -f Dockerfile --tag $TAG

echo "Saving and compressing container image"
podman save $TAG | gzip > share/container.tar.gz

echo "Looking up the image id"
podman images -q --filter=reference=$TAG > share/image-id.txt
