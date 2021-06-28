#!/bin/bash

# Install dependencies
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y qemu-utils wget nbdfuse

# Build the VM image
cd /build
rm -r /build/vm
mkdir -p /build/vm
./alpine-make-vm-image \
    --image-format qcow2 \
    --image-size 2G \
    --packages "$(cat packages)" \
    --script-chroot \
    /build/vm/dangerzone.qcow2 -- ./configure.sh

# Extract vmlinuz and initramfs
qemu-nbd -c /dev/nbd0 /build/vm/dangerzone.qcow2
mount /dev/nbd0 /mnt
cp /mnt/boot/vmlinuz-virt /build/vm
cp /mnt/boot/initramfs-virt /build/vm
umount /mnt
