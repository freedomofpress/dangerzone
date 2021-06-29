# Build the Dangerzone VM for running podman

## Build the ISO

You need vagrant: `brew install vagrant`

```sh
vagrant up
vagrant ssh -- /vagrant/build-iso.sh 
```

## Run the VM

```sh
./run-vm.sh
```

You can ssh in as the unprivileged user like this:

```sh
ssh -i ./ssh-key/id_ed25519 -o StrictHostKeyChecking=no user@192.168.65.3
```

(doesn't work yet)
