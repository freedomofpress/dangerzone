# Build the Dangerzone VM for running podman

Thanks, [alpine-make-vm-image](https://github.com/alpinelinux/alpine-make-vm-image) project. License: MIT

To build the qcow2 VM image:

```sh
docker run \
    --privileged --cap-add=ALL \
    -v $(pwd):/build ubuntu:latest /build/build-qcow2.sh
```

This will create a VM image file called `vm/dangerzone.qcow2`.

To build an ISO image:

```sh
docker run -v $(pwd):/build alpine:latest /build/build-iso.sh
```
