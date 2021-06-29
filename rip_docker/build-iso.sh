#!/bin/sh

# Following: https://wiki.alpinelinux.org/wiki/How_to_make_a_custom_ISO_image_with_mkimage

# Install dependencies
apk update
apk add alpine-sdk build-base apk-tools alpine-conf busybox fakeroot syslinux xorriso squashfs-tools sudo
apk add mtools dosfstools grub-efi
apk add p7zip

# Create a new user
adduser build -D -G abuild
echo "%abuild ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/abuild

cat << EOF > /home/build/go.sh
#!/bin/sh

cd /home/build

# Create signing keys
abuild-keygen -i -a -n

# Setup aports
wget https://gitlab.alpinelinux.org/alpine/aports/-/archive/master/aports-master.tar.gz
tar -xf aports-master.tar.gz
mv aports-master aports
cp /build/mkimg.dangerzone.sh aports/scripts/
cp /build/genapkovl-dangerzone.sh aports/scripts/
chmod +x aports/scripts/mkimg.dangerzone.sh
chmod +x aports/scripts/genapkovl-dangerzone.sh

# Make the iso
cd aports/scripts
sh mkimage.sh --tag v3.14 \
    --outdir /build/vm \
    --arch x86_64 \
    --repository http://dl-cdn.alpinelinux.org/alpine/v3.14/main \
    --repository http://dl-cdn.alpinelinux.org/alpine/v3.14/community \
    --profile dangerzone
EOF
chmod +x /home/build/go.sh

# Set up the vm dir
rm -r /build/vm
mkdir -p /build/vm
chmod 777 /build/vm

# Start the build
sudo -u build /home/build/go.sh

# Fix permissions
chmod 755 /build/vm
chmod 644 /build/vm/*
chown root:root /build/vm/*

# Extract vmlinuz and initramfs
cd /build/vm
7z x alpine-dangerzone-v3.14-x86_64.iso boot/vmlinuz-virt
7z x alpine-dangerzone-v3.14-x86_64.iso boot/initramfs-virt
mv boot/* .
rm -r boot
