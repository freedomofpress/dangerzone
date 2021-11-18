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

# Build ISO
cd vm-builder
vagrant up
vagrant ssh -- /vagrant/build-iso.sh
vagrant halt
cd ..

# Copy the ISO to resources
mkdir -p share/vm
cp vm-builder/vm/* share/vm
