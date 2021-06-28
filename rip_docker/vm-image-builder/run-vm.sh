#!/bin/bash

ROOT=$(pwd)/vm
HYPERKIT=/Applications/Docker.app/Contents/Resources/bin/com.docker.hyperkit
VPNKIT=/Applications/Docker.app/Contents/Resources/bin/com.docker.vpnkit

echo "[] Running vpnkit"
VPNKIT_SOCK=$ROOT/vpnkit.eth.sock
PIDFILE=$ROOT/vpnkit.pid
$VPNKIT --ethernet=$VPNKIT_SOCK &
echo $! > $PIDFILE
trap 'test -f $PIDFILE && kill `cat $PIDFILE` && rm $PIDFILE' EXIT

sleep 1

# echo "[] Making disk image"
# mkfile 1g $ROOT/disk.img

echo "[] Starting VM"
$HYPERKIT \
    -A -u \
    -m 2G \
    -c 2 \
    -s 0:0,hostbridge -s 31,lpc \
    -l com1,stdio \
    -s 3:0,ahci-cd,$ROOT/dangerzone.raw \
    -s 2:0,virtio-vpnkit,path=$VPNKIT_SOCK \
    -U 9efa82d7-ebd5-4287-b1cc-ac4160a39fa7 \
    -f kexec,$ROOT/vmlinuz-virt,$ROOT/initramfs-virt,"earlyprintk=serial console=ttyS0 modules=loop,squashfs,sd-mod,usb-storage"

    # -s 4:0,virtio-blk,$ROOT/disk.img \
