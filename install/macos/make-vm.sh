#!/bin/sh

# Compile hyperkit
cd vendor/hyperkit/
make || { echo 'Failed to compile hyperkit' ; exit 1; }
cd ../..

# Compile vpnkit (on Intel chips, it's too hard to compile in Apple chips)
ARCH=$(/usr/bin/arch)
if [ "$ARCH" == "i386" ]; then
    cd vendor/vpnkit/
    make -f Makefile.darwin || { echo 'Failed to compile vpnkit' ; exit 1; }
    cd ../..
fi

# Copy binaries to share
mkdir -p share/bin
cp vendor/hyperkit/build/hyperkit share/bin/hyperkit
if [ "$ARCH" == "i386" ]; then
    cp vendor/vpnkit/_build/install/default/bin/vpnkit share/bin/vpnkit
elif [ "$ARCH" == "arm64" ]; then
    # On Apple chips we copy the binary from Docker Desktop
    cp /Applications/Docker.app/Contents/Resources/bin/com.docker.vpnkit share/bin/vpnkit
fi

# Build the dangerzone-converter image
echo "Building dangerzone-converter image"
docker build dangerzone-converter --tag dangerzone.rocks/dangerzone
echo "Saving dangerzone-converter image"
docker save dangerzone.rocks/dangerzone -o vm-builder/dangerzone-converter.tar
echo "Compressing dangerzone-converter image"
gzip -f vm-builder/dangerzone-converter.tar

# Build the ISO
docker run -v $(pwd)/vm-builder:/vm-builder alpine:latest /vm-builder/build-iso.sh

# Copy the ISO to resources
mkdir -p share/vm
cp vm-builder/vm/* share/vm
