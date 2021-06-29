#!/bin/bash

ROOT=$(pwd)/vm
HYPERKIT=/Applications/Docker.app/Contents/Resources/bin/com.docker.hyperkit
VPNKIT=/Applications/Docker.app/Contents/Resources/bin/com.docker.vpnkit

VPNKIT_SOCK=$ROOT/vpnkit.eth.sock
PIDFILE=$ROOT/vpnkit.pid
$VPNKIT --ethernet=$VPNKIT_SOCK &
echo $! > $PIDFILE
trap 'test -f $PIDFILE && kill `cat $PIDFILE` && rm $PIDFILE' EXIT

$HYPERKIT \
    -A -u \
    -m 4G \
    -c 2 \
    -s 0:0,hostbridge -s 31,lpc \
    -l com1,stdio \
    -s 3:0,ahci-cd,$ROOT/alpine-dangerzone-v3.14-x86_64.iso \
    -s 2:0,virtio-vpnkit,path=$VPNKIT_SOCK \
    -U 9efa82d7-ebd5-4287-b1cc-ac4160a39fa7 \
    -f kexec,$ROOT/vmlinuz-virt,$ROOT/initramfs-virt,"earlyprintk=serial console=ttyS0 modules=loop,squashfs,sd-mod,usb-storage"
