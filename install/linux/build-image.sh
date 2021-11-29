#!/bin/sh

echo "Building container image"
podman build container --tag dangerzone.rocks/dangerzone

echo "Saving container image"
podman save dangerzone.rocks/dangerzone -o share/container.tar

echo "Compressing container image"
gzip -f share/container.tar

echo "Looking up the image id"
podman image ls dangerzone.rocks/dangerzone | grep "dangerzone.rocks/dangerzone" | tr -s ' ' | cut -d' ' -f3 > share/image-id.txt
