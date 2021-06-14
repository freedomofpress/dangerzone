# RIP Docker

Notes for removing the Docker Desktop dependency from Dangerzone.

## macOS

The most promising path forward is with [LinuxKit](https://github.com/linuxkit/linuxkit) and [HyperKit](https://github.com/moby/hyperkit). This is super helpful, a [LinuxKit config for Docker for Mac](https://github.com/linuxkit/linuxkit/blob/master/examples/docker-for-mac.md).

### Install Docker Desktop

Docker is required for linuxkit to build the VM image.

### Install LinuxKit and HyperKit

Install from homebrew:

```sh
brew tap linuxkit/linuxkit
brew install --HEAD linuxkit
brew install hyperkit
```

### Build the dangerzone VM image

```sh
linuxkit build -format kernel+initrd dangerzone.yml
```

And then try running it:

```sh
linuxkit run hyperkit -hyperkit /usr/local/bin/hyperkit -networking=vpnkit -vsock-ports=2376 -disk size=4096M -data-file ./metadata.json -kernel -uefi dangerzone
```

### Uninstall Docker Desktop

Just to make sure it isn't interfering. Click the Docker systray icon > Troubleshooting > Uninstall, and then delete Docker from Applications.




### Old stuff

Here's my attempts at installing from source, documented for posterity.

```sh
mkir -p build bin

# download pre-built linuxkit binary
cd bin
wget https://github.com/linuxkit/linuxkit/releases/download/v0.8/linuxkit-darwin-amd64
chmod +x linuxkit-darwin-amd64 
cd ..

# build hyperkit
cd build
wget https://github.com/moby/hyperkit/archive/refs/tags/v0.20210107.tar.gz
mv v0.20210107.tar.gz hyperkit-v0.20210107.tar.gz
tar -xf hyperkit-v0.20210107.tar.gz
cd hyperkit-0.20210107
make
cp ../..
ln -s build/hyperkit-0.20210107/build/hyperkit bin/hyperkit

# install dependencies for vpnkit
brew install wget opam pkg-config
opam init # only need to run this if opam wasn't installed before

# build vpnkit
cd build
# wget https://github.com/moby/vpnkit/archive/refs/tags/v0.5.0.tar.gz
wget https://github.com/micahflee/vpnkit/archive/refs/heads/ocaml-upgrade.tar.gz
mv ocaml-upgrade.tar.gz vpnkit-ocaml-upgrade.tar.gz
tar -xf vpnkit-ocaml-upgrade.tar.gz
cd vpnkit-ocaml-upgrade
make

# uggh, I keep failing at this. going to switch to homebrew
```
