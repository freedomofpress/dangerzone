# RIP Docker

Notes for removing the Docker Desktop dependency from Dangerzone.

## macOS

The most promising path forward is with [LinuxKit](https://github.com/linuxkit/linuxkit) and [HyperKit](https://github.com/moby/hyperkit). This is super helpful, a [LinuxKit config for Docker for Mac](https://github.com/linuxkit/linuxkit/blob/master/examples/docker-for-mac.md).

### Install Docker Desktop

Docker is required for linuxkit to build the VM image.

### Collect the binaries

```sh
mkdir -p bin

# download pre-built LinuxKit binary
cd bin
wget https://github.com/linuxkit/linuxkit/releases/download/v0.8/linuxkit-darwin-amd64
chmod +x linuxkit-darwin-amd64 
mv linuxkit-darwin-amd64 linuxkit
cd ..

# copy binaries from Docker Desktop
cp /Applications/Docker.app/Contents/Resources/bin/com.docker.hyperkit bin/hyperkit
cp /Applications/Docker.app/Contents/Resources/bin/com.docker.vpnkit bin/vpnkit
cp /Applications/Docker.app/Contents/Resources/bin/com.docker.cli bin/docker
```

### Build the dangerzone VM image and see if it works

```sh
./bin/linuxkit build -format kernel+initrd dangerzone.yml
```

And then try running it:

```sh
./bin/linuxkit run hyperkit \
    -hyperkit ./bin/hyperkit \
    -vpnkit ./bin/vpnkit \
    -data-file ./metadata.json \
    -networking=vpnkit \
    -vsock-ports=2376 \
    -disk size=4096M \
    -mem 2048 \
    -kernel dangerzone
```

And see if it works:

```sh
./bin/docker -H unix://dangerzone-state/guest.00000948 ps
```

Inside the VM you can shutdown with `poweroff`.

### Ooh, almost there

```
$ ./bin/docker -H unix://dangerzone-state/guest.00000948 run hello-world
Unable to find image 'hello-world:latest' locally
latest: Pulling from library/hello-world
b8dfde127a29: Pull complete 
Digest: sha256:9f6ad537c5132bcce57f7a0a20e317228d382c3cd61edae14650eec68b2b345c
Status: Downloaded newer image for hello-world:latest
docker: Error response from daemon: OCI runtime create failed: container_linux.go:349: starting container process caused "process_linux.go:449: container init caused \"process_linux.go:432: running prestart hook 0 caused \\\"fork/exec /proc/7/exe: no such file or directory\\\"\"": unknown.
ERRO[0003] error waiting for container: context canceled
```
