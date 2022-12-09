#!/bin/sh

echo "Building container image"
docker build container --platform linux/amd64 --tag dangerzone.rocks/dangerzone

echo "Saving and compressing container image"
docker save dangerzone.rocks/dangerzone | gzip > share/container.tar.gz

echo "Looking up the image id"
docker image ls dangerzone.rocks/dangerzone | grep "dangerzone.rocks/dangerzone" | tr -s ' ' | cut -d' ' -f3 > share/image-id.txt
