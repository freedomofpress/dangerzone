#!/bin/sh

# Compile hyperkit
cd vendor/hyperkit/
make || { echo 'Failed to compile hyperkit' ; exit 1; }
cd ../..

# Compile vpnkit
cd vendor/vpnkit/
make -f Makefile.darwin || { echo 'Failed to compile vpnkit' ; exit 1; }
cd ../..

# Copy binaries to share
mkdir -p share/bin
cp vendor/hyperkit/build/hyperkit share/bin/hyperkit
cp vendor/vpnkit/_build/install/default/bin/vpnkit share/bin/vpnkit

# Build the dangerzone-converter image
echo "Building dangerzone-converter image"
docker build dangerzone-converter --tag dangerzone.rocks/dangerzone
echo "Saving dangerzone-converter image"
docker save dangerzone.rocks/dangerzone -o vm-builder/dangerzone-converter.tar
echo "Compressing dangerzone-converter image"
gzip vm-builder/dangerzone-converter.tar

# Build the ISO
docker run -v $(pwd)/vm-builder:/vm-builder alpine:latest /vm-builder/build-iso.sh

# Copy the ISO to resources
mkdir -p share/vm
cp vm-builder/vm/* share/vm
