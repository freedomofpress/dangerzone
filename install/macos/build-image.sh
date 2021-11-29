#!/bin/sh

echo "Building container image"
docker build container --tag dangerzone.rocks/dangerzone

echo "Saving container image"
docker save dangerzone.rocks/dangerzone -o share/container.tar

echo "Compressing container image"
gzip -f share/container.tar

echo "Looking up the image id"
docker image ls dangerzone.rocks/dangerzone | grep "dangerzone.rocks/dangerzone" | tr -s ' ' | cut -d' ' -f3 > share/image-id.txt
