#!/bin/sh

set -euo pipefail

TAG=dangerzone.rocks/dangerzone:latest

container_runtime() {
	if hash podman &>/dev/null; then
		podman "$@"
	elif hash docker &>/dev/null; then
		docker "$@"
	else
		echo 'No container runtime installed.' >&2
		exit 1
	fi
}

echo "Building container image" >&2
container_runtime build --pull dangerzone/ -f Dockerfile --tag "$TAG"

echo "Saving and compressing container image" >&2
container_runtime save "$TAG" | gzip > share/container.tar.gz

echo "Looking up the image id" >&2
container_runtime images -q --filter=reference="$TAG" > share/image-id.txt
