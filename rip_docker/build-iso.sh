#!/bin/sh

cd ~/

# Add build user
sudo adduser build -D -G abuild
sudo sh -c 'echo "%abuild ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/abuild'

# Create signing keys
sudo -u build abuild-keygen -i -a -n

# Setup aports
if [ -d aports ]; then
    echo "already downloaded"
else
    wget https://gitlab.alpinelinux.org/alpine/aports/-/archive/master/aports-master.tar.gz
    tar -xf aports-master.tar.gz
    mv aports-master aports
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
sudo -u build sh mkimage.sh --tag v3.14 \
    --outdir /vagrant/vm \
    --arch x86_64 \
    --repository http://dl-cdn.alpinelinux.org/alpine/v3.14/main \
    --repository http://dl-cdn.alpinelinux.org/alpine/v3.14/community \
    --profile dangerzone

# Fix permissions
chown -R vagrant:vangrant /vagrant/vm
chmod 755 /vagrant/vm
chmod 644 /vagrant/vm/*

# Extract vmlinuz and initramfs
cd /vagrant/vm
7z x alpine-dangerzone-v3.14-x86_64.iso boot/vmlinuz-virt
7z x alpine-dangerzone-v3.14-x86_64.iso boot/initramfs-virt
mv boot/* .
rm -r boot
