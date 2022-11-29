#!/bin/sh

set -e

echo "Building container image"
podman build container --platform linux/amd64 --tag dangerzone.rocks/dangerzone

echo "Saving and compressing container image"
podman save dangerzone.rocks/dangerzone | gzip > share/container.tar.gz

echo "Looking up the image id"
podman image ls dangerzone.rocks/dangerzone | grep "dangerzone.rocks/dangerzone" | tr -s ' ' | cut -d' ' -f3 > share/image-id.txt
