# Build the Dangerzone VM for running podman

## Build the podman container storage (with vagrant)

You need vagrant: `brew install vagrant`

## Build the ISO image (with docker)

```sh
docker run -v $(pwd):/build alpine:latest /build/build-iso.sh
```

## Run the VM

```sh
./run-vm.sh
```

You can ssh in as the unprivileged user like this:

```sh
ssh -i ./ssh-key/id_ed25519 -o StrictHostKeyChecking=no user@192.168.65.3
```
