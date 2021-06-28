# Build the Dangerzone VM for running podman

To build an ISO image:

```sh
docker run -v $(pwd):/build alpine:latest /build/build-iso.sh
```

To run the VM:

```sh
./run-vm.sh
```
