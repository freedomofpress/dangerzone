#!/bin/sh -e

HOSTNAME="$1"
if [ -z "$HOSTNAME" ]; then
	echo "usage: $0 hostname"
	exit 1
fi

cleanup() {
	rm -rf "$tmp"
}

rc_add() {
	mkdir -p "$tmp"/etc/runlevels/"$2"
	ln -sf /etc/init.d/"$1" "$tmp"/etc/runlevels/"$2"/"$1"
}

tmp="$(mktemp -d)"
trap cleanup EXIT

# Copy /etc
cp -r /vagrant/etc "$tmp"
chown -R root:root "$tmp"/etc

# Fix permissions and add containers to /etc/container-data, temporarily
for WEIRD_FILE in $(find /home/user/.local/share/containers -perm 000); do
	chmod 600 $WEIRD_FILE
done
cp -r /home/user/.local/share/containers "$tmp"/etc/container-data

# Start cgroups, required by podman
rc_add cgroups boot

# Start dropbear (ssh server)
rc_add dropbear boot

# Initialize the dangerzone VM
rc_add dangerzone boot

# Other init scripts
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
