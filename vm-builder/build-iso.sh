#!/bin/sh

ALPINE_TAG=v3.14.3

# Install dependencies
apk add alpine-sdk build-base apk-tools alpine-conf busybox fakeroot xorriso squashfs-tools mtools dosfstools grub-efi p7zip abuild sudo

# Make keys for build
abuild-keygen -i -a -n

# Setup aports
cd ~/
wget https://gitlab.alpinelinux.org/alpine/aports/-/archive/master/aports-master.tar.gz
tar -xf ~/aports-master.tar.gz
mv ~/aports-master ~/aports
cp /vm-builder/mkimg.dz.sh ~/aports/scripts/
cp /vm-builder/genapkovl-dz.sh ~/aports/scripts/
chmod +x ~/aports/scripts/mkimg.dz.sh
chmod +x ~/aports/scripts/genapkovl-dz.sh

# Set up the vm dir
rm -r /vm-builder/vm
mkdir -p /vm-builder/vm
chmod 777 /vm-builder/vm

# Make the iso
cd ~/aports/scripts
./mkimage.sh --tag "$ALPINE_TAG" \
    --outdir /vm-builder/vm \
    --arch $(uname -m) \
    --repository http://dl-cdn.alpinelinux.org/alpine/v3.14/main \
    --repository http://dl-cdn.alpinelinux.org/alpine/v3.14/community \
    --profile dz
mv /vm-builder/vm/alpine-dz-${ALPINE_TAG}-$(uname -m).iso /vm-builder/vm/dangerzone.iso

# Fix permissions
chmod 755 /vm-builder/vm
chmod 644 /vm-builder/vm/*

# Extract vmlinuz and initramfs
cd /vm-builder/vm
7z x dangerzone.iso boot/vmlinuz-virt
7z x dangerzone.iso boot/initramfs-virt
mv boot/* .
rm -r boot
mv vmlinuz-virt kernel
mv initramfs-virt initramfs.img
