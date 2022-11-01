#!/bin/bash

# Development script for installing Podman on Ubuntu Focal. Mainly to be used as
# part of our CI pipelines, where we may install Podman on environments that
# don't have sudo.

set -e

if [[ "$EUID" -ne 0 ]]; then
    SUDO=sudo
else
    SUDO=
fi

provide() {
    $SUDO apt-get update
    $SUDO apt-get install curl wget gnupg2 -y
    source /etc/os-release
    $SUDO sh -c "echo 'deb http://download.opensuse.org/repositories/devel:/kubic:/libcontainers:/stable/xUbuntu_${VERSION_ID}/ /' \
      > /etc/apt/sources.list.d/devel:kubic:libcontainers:stable.list"
    wget -nv https://download.opensuse.org/repositories/devel:kubic:libcontainers:stable/xUbuntu_${VERSION_ID}/Release.key -O- \
      | $SUDO apt-key add -
    $SUDO apt-get update -qq -y
}

install() {
    $SUDO apt-get -qq --yes install podman
    podman --version
}

if [[ "$1" == "--repo-only" ]]; then
    provide
elif [[ "$1" == "" ]]; then
    provide
    install
else
    echo "Unexpected argument: $1"
    echo "Usage: $0 [--repo-only]"
    exit 1
fi
