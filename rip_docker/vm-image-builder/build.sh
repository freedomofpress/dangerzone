#!/bin/bash

# Install dependencies
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y qemu-utils wget nbdfuse

# Build the VM image
cd /build
mkdir -p /build/out
./alpine-make-vm-image \
    --image-format qcow2 \
    --image-size 2G \
    --packages "$(cat packages)" \
    --script-chroot \
    /build/out/dangerzone.qcow2 -- ./configure.sh

# Extract vmlinuz and initramfs
qemu-nbd -c /dev/nbd0 /build/out/dangerzone.qcow2
mount /dev/nbd0 /mnt
cp /mnt/boot/vmlinuz-virt /build/out
cp /mnt/boot/initramfs-virt /build/out
umount /mnt
