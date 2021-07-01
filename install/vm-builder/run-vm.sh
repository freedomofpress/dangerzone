#!/bin/bash

ROOT=$(pwd)/vm
HYPERKIT=/Applications/Docker.app/Contents/Resources/bin/com.docker.hyperkit
VPNKIT=/Applications/Docker.app/Contents/Resources/bin/com.docker.vpnkit

SSHD_PORT=4445
SSHD_TUNNEL_PORT=4446

tmp="$(mktemp -d)"
trap rm -rf "$tmp" EXIT

# make ssh keys
/usr/bin/ssh-keygen \
    -t ed25519 \
    -C dangerzone-host \
    -N "" \
    -f "$tmp/host_ed25519"
/usr/bin/ssh-keygen \
    -t ed25519 \
    -C dangerzone-client \
    -N "" \
    -f "$tmp/client_ed25519"

# run sshd
SSHD_PIDFILE=$ROOT/sshd.pid
/usr/sbin/sshd \
    -4 \
    -E $ROOT/sshd.log \
    -o PidFile=$ROOT/sshd.pid \
    -o HostKey=$tmp/host_ed25519 \
    -o ListenAddress=127.0.0.1:$SSHD_PORT \
    -o AllowUsers=$(whoami) \
    -o PasswordAuthentication=no \
    -o PubkeyAuthentication=yes \
    -o Compression=yes \
    -o ForceCommand=/usr/bin/whoami \
    -o UseDNS=no \
    -o AuthorizedKeysFile=$tmp/client_ed25519.pub &
echo $! > $SSHD_PIDFILE
trap 'test -f $SSHD_PIDFILE && kill `cat $SSHD_PIDFILE` && rm $SSHD_PIDFILE' EXIT

# create disk image
cd $ROOT
cat > info.json << EOF
{
    "id_ed25519": "$(cat $tmp/client_ed25519 | awk '{printf "%s\\n", $0}')",
    "id_ed25519.pub": "$(cat $tmp/client_ed25519.pub)",
    "user": "$(whoami)",
    "ip": "192.168.65.2",
    "port": $SSHD_PORT,
    "tunnel_port": $SSHD_TUNNEL_PORT
}
EOF
python3 -c 's=open("info.json").read(); open("disk.img", "wb").write(s.encode()+b"\x00"*(512*1024-len(s)))'

# run vpnkit
VPNKIT_SOCK=$ROOT/vpnkit.eth.sock
VPNKIT_PIDFILE=$ROOT/vpnkit.pid
$VPNKIT \
    --ethernet=$VPNKIT_SOCK \
    --gateway-ip 192.168.65.1 \
    --host-ip 192.168.65.2 \
    --lowest-ip 192.168.65.3 \
    --highest-ip 192.168.65.254 &
echo $! > $VPNKIT_PIDFILE
trap 'test -f $VPNKIT_PIDFILE && kill `cat $VPNKIT_PIDFILE` && rm $VPNKIT_PIDFILE' EXIT

# run hyperkit
$HYPERKIT \
    -F $ROOT/hyperkit.pid \
    -A -u \
    -m 4G \
    -c 2 \
    -s 0:0,hostbridge -s 31,lpc \
    -l com1,stdio \
    -s 1:0,ahci-cd,$ROOT/dangerzone.iso \
    -s 2:0,virtio-vpnkit,path=$VPNKIT_SOCK \
    -s 3:0,virtio-blk,$ROOT/disk.img \
    -U 9efa82d7-ebd5-4287-b1cc-ac4160a39fa7 \
    -f kexec,$ROOT/kernel,$ROOT/initramfs.img,"earlyprintk=serial console=ttyS0 modules=loop,squashfs,sd-mod"
