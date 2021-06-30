#!/bin/bash

ROOT=$(pwd)/vm
HYPERKIT=/Applications/Docker.app/Contents/Resources/bin/com.docker.hyperkit
VPNKIT=/Applications/Docker.app/Contents/Resources/bin/com.docker.vpnkit

VPNKIT_SOCK=$ROOT/vpnkit.eth.sock
PIDFILE=$ROOT/vpnkit.pid
$VPNKIT \
    --ethernet=$VPNKIT_SOCK \
    --gateway-ip 192.168.65.1 \
    --host-ip 192.168.65.2 \
    --lowest-ip 192.168.65.3 \
    --highest-ip 192.168.65.254 &
echo $! > $PIDFILE
trap 'test -f $PIDFILE && kill `cat $PIDFILE` && rm $PIDFILE' EXIT

$HYPERKIT \
    -F $ROOT/hyperkit.pid \
    -A -u \
    -m 4G \
    -c 2 \
    -s 0:0,hostbridge -s 31,lpc \
    -l com1,stdio \
    -s 1:0,ahci-cd,$ROOT/dangerzone.iso \
    -s 2:0,virtio-vpnkit,path=$VPNKIT_SOCK \
    -U 9efa82d7-ebd5-4287-b1cc-ac4160a39fa7 \
    -f kexec,$ROOT/kernel,$ROOT/initramfs.img,"earlyprintk=serial console=ttyS0 modules=loop,squashfs,sd-mod"
