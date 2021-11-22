#!/bin/sh

echo "Building dangerzone-converter image"
docker build dangerzone-converter --tag dangerzone.rocks/dangerzone

echo "Saving dangerzone-converter image"
docker save dangerzone.rocks/dangerzone -o share/dangerzone-converter.tar

echo "Compressing dangerzone-converter image"
gzip -f share/dangerzone-converter.tar

echo "Looking up the image id"
docker image ls dangerzone.rocks/dangerzone | grep "dangerzone.rocks/dangerzone" | tr -s ' ' | cut -d' ' -f3 > share/image-id.txt
