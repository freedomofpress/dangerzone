#!/bin/sh -e

HOSTNAME="$1"
if [ -z "$HOSTNAME" ]; then
	echo "usage: $0 hostname"
	exit 1
fi

cleanup() {
	rm -rf "$tmp"
}

makefile() {
	OWNER="$1"
	PERMS="$2"
	FILENAME="$3"
	cat > "$FILENAME"
	chown "$OWNER" "$FILENAME"
	chmod "$PERMS" "$FILENAME"
}

rc_add() {
	mkdir -p "$tmp"/etc/runlevels/"$2"
	ln -sf /etc/init.d/"$1" "$tmp"/etc/runlevels/"$2"/"$1"
}

tmp="$(mktemp -d)"
trap cleanup EXIT

mkdir -p "$tmp"/etc/apk
makefile root:root 0644 "$tmp"/etc/apk/world <<EOF
alpine-base
openssh
podman
EOF

# Custom sshd config
mkdir -p "$tmp"/etc/ssh
makefile root:root 0644 "$tmp"/etc/ssh/sshd_config <<EOF
AuthorizedKeysFile .ssh/authorized_keys
AllowTcpForwarding no
GatewayPorts no
X11Forwarding no
Subsystem sftp /usr/lib/ssh/sftp-server
UseDNS no
PasswordAuthentication no
EOF

# Dangerzone alpine setup
mkdir -p "$tmp"/root
makefile root:root 0644 "$tmp"/root/answers.txt <<EOF
KEYMAPOPTS="us us"
HOSTNAMEOPTS="-n dangerzone"
INTERFACESOPTS="auto lo
iface lo inet loopback

auto eth0
iface eth0 inet dhcp
    hostname dangerzone
"
DNSOPTS="-d example.com 4.4.4.4"
TIMEZONEOPTS="-z UTC"
SSHDOPTS="-c openssh"
EOF

mkdir -p "$tmp"/etc/init.d
makefile root:root 0644 "$tmp"/etc/init.d/dangerzone <<EOF
#!/sbin/openrc-run
name="Dangerzone init script"
start_pre() {
	/sbin/setup-alpine -f /root/answers.txt -e -q
}
EOF

# Start cgroups, required by podman
rc_add cgroups boot

# Start sshd
rc_add sshd boot

# Run setup-alpine
rc_add dangerzone boot

rc_add devfs sysinit
rc_add dmesg sysinit
rc_add mdev sysinit
rc_add hwdrivers sysinit
rc_add modloop sysinit

rc_add hwclock boot
rc_add modules boot
rc_add sysctl boot
rc_add hostname boot
rc_add bootmisc boot
rc_add syslog boot

rc_add mount-ro shutdown
rc_add killprocs shutdown
rc_add savecache shutdown

tar -c -C "$tmp" etc | gzip -9n > $HOSTNAME.apkovl.tar.gz
