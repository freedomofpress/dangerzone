#!/bin/sh

# Set up podman
sudo modprobe fuse
sudo modprobe tun
sudo rc-update add cgroups
sudo rc-service cgroups start
sudo -u user podman system prune -a -f

# Build the podman container
cd /opt/dangerzone-converter
sudo -u user podman build . --tag dangerzone

# Setup aports
cd ~/
if [ -d ~/aports ]; then
    echo "already downloaded"
else
    wget https://gitlab.alpinelinux.org/alpine/aports/-/archive/master/aports-master.tar.gz
    tar -xf ~/aports-master.tar.gz
    mv ~/aports-master ~/aports
fi
cp /vagrant/mkimg.dangerzone.sh ~/aports/scripts/
cp /vagrant/genapkovl-dangerzone.sh ~/aports/scripts/
chmod +x ~/aports/scripts/mkimg.dangerzone.sh
chmod +x ~/aports/scripts/genapkovl-dangerzone.sh

# Set up the vm dir
rm -r /vagrant/vm
mkdir -p /vagrant/vm
chmod 777 /vagrant/vm

# Make the iso
cd ~/aports/scripts
sudo -u user sh mkimage.sh --tag v3.14 \
    --outdir /vagrant/vm \
    --arch x86_64 \
    --repository http://dl-cdn.alpinelinux.org/alpine/v3.14/main \
    --repository http://dl-cdn.alpinelinux.org/alpine/v3.14/community \
    --profile dangerzone
mv alpine-dangerzone-v3.14-x86_64.iso dangerzone.iso

# Fix permissions
chmod 755 /vagrant/vm
chmod 644 /vagrant/vm/*

# Extract vmlinuz and initramfs
cd /vagrant/vm
7z x dangerzone.iso boot/vmlinuz-virt
7z x dangerzone.iso boot/initramfs-virt
mv boot/* .
rm -r boot
mv vmlinuz-virt kernel
mv initramfs-virt initramfs.img
