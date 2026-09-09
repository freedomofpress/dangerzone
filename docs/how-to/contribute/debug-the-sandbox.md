# Debug the sandbox

When a conversion fails inside the sandbox, or when you work on the container image, it helps to see what happens inside it. This guide shows how to get gVisor logs out of a conversion and how to open a shell in the sandbox image.

## Get the sandbox logs for a conversion

Pass `--debug` to the CLI. Dangerzone then starts the container with `RUNSC_DEBUG=1` and prints the gVisor logs together with the conversion output:

```sh
dangerzone-cli --debug the-document.pdf
```

From a source checkout, `DANGERZONE_DEV=1 poetry run dangerzone-cli --debug ...` does the same.

## Open a shell in the sandbox image

The image contains a shell, so you can inspect it as root, outside of gVisor:

=== "Linux"

    ```sh
    podman run --rm -it --user root --entrypoint /bin/sh \
        ghcr.io/freedomofpress/dangerzone/v1
    ```

=== "macOS and Windows"

    Use the Podman embedded in Dangerzone, through `dangerzone-machine raw`:

    ```sh
    dangerzone-machine raw run --rm -it --user root --entrypoint /bin/sh \
        ghcr.io/freedomofpress/dangerzone/v1
    ```

    See the [dangerzone-machine reference](../../reference/cli/dangerzone-machine.md#location) for the full path of the command.

Inside, the conversion code lives in the `dangerzone.conversion` Python package, and a conversion is what Dangerzone runs as `/usr/bin/python3 -m dangerzone.conversion.doc_to_pixels` with the document on standard input. See [Sandbox protocol](../../reference/sandbox-protocol.md) for what it reads and writes.

!!! note

    Running the image by hand like this skips the hardening that Dangerzone applies (no network, dropped capabilities, seccomp profile, gVisor, no user mapping). Only do it with images and documents you trust, or in a disposable environment. You can get a shell under gVisor as well, but you won't get a terminal back, so its usefulness is limited.

## Use a locally built image

To test changes to the image itself, build it from the [dangerzone-image](https://github.com/freedomofpress/dangerzone-image) repository, store the result as `share/container.tar`, and bypass signature checks as described in [Use a local container image](build-from-source.md#using-a-local-container-image).

## Reset everything

If the local image or the Podman machine is in a broken state:

```sh
dangerzone-machine reset     # macOS and Windows: remove machine and image
dangerzone-image upgrade     # fetch a fresh, signed image
```

On Linux, remove the image with `podman rmi ghcr.io/freedomofpress/dangerzone/v1` and run `dangerzone-image upgrade`.
