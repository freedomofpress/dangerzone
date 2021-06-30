#!/bin/sh

# Extract hyperkit and vpnkit from Docker Desktop
mkdir -p share/bin
cp /Applications/Docker.app/Contents/Resources/bin/com.docker.hyperkit share/bin/hyperkit
cp /Applications/Docker.app/Contents/Resources/bin/com.docker.vpnkit share/bin/vpnkit

# Build ISO
cd install/vm-builder
vagrant up
vagrant ssh -- /vagrant/build-iso.sh
vagrant down
cd ../..

# Copy the ISO to resources
mkdir -p share/vm
cp install/vm-builder/vm/* share/vm
