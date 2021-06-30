# Build the Dangerzone VM for running podman

## Build the ISO

You need vagrant: `brew install vagrant`

```sh
vagrant up
vagrant ssh -- /vagrant/build-iso.sh
vagrant destroy
```

This takes awhile to run. It:

- Builds a new `dangerzone-converter` docker image
- Builds an ISO, which includes a copy of this image
- Outputs the ISO, as well as vmlinuz and initramfs files, in the `vm` folder

## Run the VM

```sh
./run-vm.sh
```

You can ssh in as the unprivileged user like this (you need to `brew install socat`):

```sh
ssh -i ./ssh-key/id_ed25519 \
    -o LogLevel=FATAL \
    -o Compression=yes \
    -o IdentitiesOnly=yes \
    -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null \
    -o "ProxyCommand nc -U /Users/user/code/dangerzone/rip_docker/vm/connect" \
    -v \
    user@localhost
```

(doesn't work yet)


Notes on sshd:

```
# Generate keys
rm -r state
mkdir state
ssh-keygen -t ed25519 -C dangerzone-vm-key -N "" -f state/host_ed25519
ssh-keygen -t ed25519 -C dangerzone-vm-key -N "" -f state/client_ed25519

# start sshd service
/usr/sbin/sshd -4 \
    -o HostKey=$(pwd)/state/host_ed25519 \
    -o ListenAddress=127.0.0.1:4444 \
    -o AllowUsers=$(whoami) \
    -o PasswordAuthentication=no \
    -o PubkeyAuthentication=yes \
    -o Compression=yes \
    -o ForceCommand=/usr/bin/whoami \
    -o UseDNS=no \
    -o AuthorizedKeysFile=$(pwd)/state/client_ed25519.pub

# in the vm, making an ssh tunnel

 ssh -o StrictHostKeyChecking=no -N -R 52038:127.0.0.1:22 -p 52039 user@192.168.65.2

```