#!/bin/sh

echo "Building dangerzone-converter image"
podman build dangerzone-converter --tag dangerzone.rocks/dangerzone

echo "Saving dangerzone-converter image"
podman save dangerzone.rocks/dangerzone -o share/dangerzone-converter.tar

echo "Compressing dangerzone-converter image"
gzip -f share/dangerzone-converter.tar

echo "Looking up the image id"
podman image ls dangerzone.rocks/dangerzone | grep "dangerzone.rocks/dangerzone" | tr -s ' ' | cut -d' ' -f3 > share/image-id.txt
