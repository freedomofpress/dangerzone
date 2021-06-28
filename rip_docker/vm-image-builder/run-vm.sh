#!/bin/bash

ROOT=$(pwd)/vm

echo "[] Running vpnkit"
VPNKIT_SOCK=$ROOT/vpnkit.eth.sock
PIDFILE=$ROOT/vpnkit.pid
vpnkit --ethernet=$VPNKIT_SOCK &
echo $! > $PIDFILE
trap 'test -f $PIDFILE && kill `cat $PIDFILE` && rm $PIDFILE' EXIT

sleep 1

# echo "[] Making disk image"
# mkfile 1g $ROOT/disk.img

echo "[] Starting VM"
hyperkit \
    -A -u \
    -m 2G \
    -c 2 \
    -s 0:0,hostbridge -s 31,lpc \
    -l com1,stdio \
    -s 1:0,ahci-hd,file://$ROOT/dangerzone.qcow2,format=qcow \
    -s 2:0,virtio-vpnkit,path=$VPNKIT_SOCK \
    -U 9efa82d7-ebd5-4287-b1cc-ac4160a39fa7 \
    -f kexec,$ROOT/vmlinuz-virt,$ROOT/initramfs-virt,"earlyprintk=serial console=ttyS0 modules=loop,squashfs,sd-mod,usb-storage"

    # -s 4:0,virtio-blk,$ROOT/disk.img \