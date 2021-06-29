#!/bin/bash

ROOT=$(pwd)/vm
HYPERKIT=/Applications/Docker.app/Contents/Resources/bin/com.docker.hyperkit
VPNKIT=/Applications/Docker.app/Contents/Resources/bin/com.docker.vpnkit

# VPNKIT_SOCK=$ROOT/vpnkit.eth.sock
# PIDFILE=$ROOT/vpnkit.pid
# $VPNKIT \
#     --ethernet=$VPNKIT_SOCK \
#     --gateway-ip 192.168.65.1 \
#     --host-ip 192.168.65.2 \
#     --lowest-ip 192.168.65.3 \
#     --highest-ip 192.168.65.254 &
# echo $! > $PIDFILE
# trap 'test -f $PIDFILE && kill `cat $PIDFILE` && rm $PIDFILE' EXIT

$HYPERKIT \
    -F $ROOT/hyperkit.pid \
    -A -u \
    -m 4G \
    -c 2 \
    -s 0:0,hostbridge -s 31,lpc \
    -l com1,stdio \
    -s 1:0,ahci-cd,$ROOT/alpine-dangerzone-v3.14-x86_64.iso \
    -s 2:0,virtio-net \
    -U 9efa82d7-ebd5-4287-b1cc-ac4160a39fa7 \
    -f kexec,$ROOT/vmlinuz-virt,$ROOT/initramfs-virt,"earlyprintk=serial console=ttyS0 modules=loop,squashfs,sd-mod,usb-storage vpnkit.connect=connect://2/1999"

# hyperkit 
#     -c 1 -m 1024M 
#     -u -A -H 
#     -U 386bba5a-5dc4-3ac2-95c9-cf0b9a29b352 
#     -s 0:0,hostbridge 
#     -s 2:0,virtio-net 
#     -s 5,virtio-rnd 
#     -s 31,lpc 
#     -l com1,autopty=primary/pty,log=/Library/Logs/Multipass/primary-hyperkit.log 
#     -s 1:0,virtio-blk,file://primary/ubuntu-20.04-server-cloudimg-amd64.img?sync=os&buffered=1,format=qcow,qcow-config=discard=true;compact_after_unmaps=262144;keep_erased=262144;runtime_asserts=false 
#     -s 1:1,ahci-cd,primary/cloud-init-config.iso 
#     -f kexec,primary/ubuntu-20.04-server-cloudimg-amd64-vmlinuz-generic,primary/ubuntu-20.04-server-cloudimg-amd64-initrd-generic,earlyprintk=serial console=ttyS0 root=/dev/vda1 rw panic=1 no_timer_check
