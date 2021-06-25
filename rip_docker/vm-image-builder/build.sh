#!/bin/bash
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y qemu-utils wget nbdfuse
cd /build
./alpine-make-vm-image \
    --image-format qcow2 \
    --image-size 2G \
    --packages "$(cat packages)" \
    --script-chroot \
    dangerzone.qcow2 -- ./configure.sh
