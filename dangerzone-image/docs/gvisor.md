# gVisor integration

> [!NOTE]
> **Update on 2025-01-13:** There is no longer a copied container image under
> `/home/dangerzone/dangerzone-image/rootfs`. We now reuse the same container
> image both for the inner and outer container. See
> [#1048](https://github.com/freedomofpress/dangerzone/issues/1048).

Dangerzone has relied on the container runtime available in each supported
operating system (Docker Desktop on Windows / macOS, Podman on Linux) to isolate
the host from the sanitization process. The problem with this type of isolation
is that it exposes a rather large attack surface; the Linux kernel.

[gVisor](https://gvisor.dev/) is an application kernel, that emulates a
substantial portion of the Linux Kernel API in Go. What's more interesting to
Dangerzone is that it also offers an OCI runtime (`runsc`) that enables
containers to transparently run this application kernel.

As of writing this, Dangerzone uses two containers to sanitize a document:
* The first container reads a document from stdin, converts each page to pixels,
  and writes them to stdout.
* The second container reads the pixels from a mounted volume (the host has
  taken care of this), and saves the final PDF to another mounted volume.

Our threat model considers the computation and output of the first container
as **untrusted**, and the computation and output of the second container as
trusted. For this reason, and because we are about to remove the need for the
second container, our integration plan will focus on the first container.

## Design overview

Our integration goals are to:
* Make gVisor available to all of our supported platforms.
* Do not ask from users to run any commands on their system to do so.

Because gVisor does not support Windows and macOS systems out of the box,
Dangerzone will be responsible for "shipping" gVisor to those users. It will do
so using nested containers:
* The **outer** container is the Docker/Podman container that Dangerzone uses
  already. This container acts as our **portability** layer. It's main purpose
  is to bundle all the necessary configuration files and program to run gVisor
  in all of our platforms.
* The **inner** container is the gVisor container, created with `runsc`. This
  container acts as our **isolation layer**. It is responsible for running the
  Python code that rasterizes a document, in a way that will be fully isolated
  from the host.

### Building the container image

This nested container approach directly affects the container image as well,
which will also have two layers:
* The **outer** container image will contain just Python3 and `runsc`, the
  latter downloaded from the official gVisor website. It will also contain an
  entrypoint that will launch `runsc`. Finally, it will contain the **inner**
  container image (see below) as filesystem clone under
  `/dangerzone-image/rootfs`.
* The **inner** container image is practically the original Dangerzone image, as
  we've always built it, which contains the necessary tooling to rasterize a
  document.

### Spawning the container

Spawning the container now becomes a multi-stage process:

The `Container` isolation provider spawns the container as before, with the
following changes:

* It adds the `SYS_CHROOT` Linux capability, which was previously dropped, to
  the **outer** container.  This capability is necessary to run `runsc`
  rootless, and is not inherited by the **inner** container.
* It removes the `--userns keep-id` argument, which mapped the user outside the
  container to the same UID (normally `1000`) within the container. This was
  originally required when we were mounting host directories within the
  container, but this no longer applies to the gVisor integration. By removing
  this flag, the host user maps to the root user within the container (UID `0`).
  - In distributions that offer Podman version 4 or greater, we use the
    `--userns nomap` flag. This flag greatly minimizes the attack surface,
    since the host user is not mapped within the container at all.
* We use our custom seccomp policy across container engines, since some do not
  allow the `ptrace` syscall (see
  [#846](https://github.com/freedomofpress/dangerzone/issues/846)).
* It labels the **outer** container with the `container_engine_t` SELinux label.
  This label is reserved for running a container engine within a container, and
  is necessary in environments where SELinux is enabled in enforcing mode (see
  [#880](https://github.com/freedomofpress/dangerzone/issues/880)).

Then, the following happens when Podman/Docker spawns the container:

1. _(outer container)_ The entrypoint code finds from `sys.argv` the command
   that Dangerzone passed to the `docker run` / `podman run` invocation.
   Typically, this command is:

   ```
   /usr/bin/python3 -m dangerzone.conversion.doc_to_pixels
   ```

2. _(outer container)_ The entrypoint code then creates an OCI config for
   `runsc` with the following properties:
   * Use UID/GID 1000 in the **inner** container image.
   * Run the command we detected on step 1.
   * Drop all Linux capabilities.
   * Limit the number of open files to 4096.
   * Use the `/dangerzone-image/rootfs` directory as the root path for the
     **inner** container.
   * Mount a gVisor view of the `procfs` hierarchy under `/proc` , and then
     mount `tmpfs` in the `/dev`, `/sys` and `/tmp` mount points. This way, no
     host-specific info may leak to the **inner** container.
     - Mount `tmpfs` on some more mountpoints where we want write access.
3. _(outer container)_ If `RUNSC_DEBUG` has been specified, add some debug
   arguments to `runsc` (applies to development environments only).
4. _(outer container)_ If `RUNSC_FLAGS` has been specified, pass some
   user-specified flags to `runsc` (applies to development environments only).
5. _(outer container)_ Spawn `runsc` as a Python subprocess, and wait for it to
   complete.
6. _(inner container)_ Read the document from stdin and write pixels to stdout.
   - In practice, nothing changes here, as far as the document conversion is
     concerned. The Python process transparently uses the emulated Linux Kernel
     API that gVisor provides.
7. _(outer container)_ Exit the container with the same exit code as the inner
   container.

## Implementation details

### Creating the outer container image

In order to achieve the above, we add one more build stage in our Dockerfile
(see [multi-stage builds](https://docs.docker.com/build/building/multi-stage/))
that copies the result of the previous stages under `/dangerzone-image/rootfs`.
Also, we install `runsc` and Python, and copy our entrypoint to that layer.

Here's how it looks like:

```dockerfile
# NOTE: The following lines are appended to the end of our original Dockerfile.

# Install some commands required by the entrypoint.
FROM alpine:latest
RUN apk --no-cache -U upgrade && \
    apk --no-cache add \
    python3 \
    su-exec

# Add the previous build stage (`dangerzone-image`) as a filesystem clone under
# the /dangerzone-image/rootfs directory.
RUN mkdir --mode=0755 -p /dangerzone-image/rootfs
COPY --from=dangerzone-image / /dangerzone-image/rootfs

# Download and install gVisor, based on the official instructions.
RUN GVISOR_URL="https://storage.googleapis.com/gvisor/releases/release/latest/$(uname -m)"; \
    wget "${GVISOR_URL}/runsc" "${GVISOR_URL}/runsc.sha512" && \
    sha512sum -c runsc.sha512 && \
    rm -f runsc.sha512 && \
    chmod 555 runsc /entrypoint.py && \
    mv runsc /usr/bin/

COPY gvisor_wrapper/entrypoint.py /
ENTRYPOINT ["/entrypoint.py"]
```

### OCI config

The OCI config that gets produced is similar to this:

```json
{
    "ociVersion": "1.0.0",
    "process": {
        "user": {
            "uid": 1000,
            "gid": 1000
        },
        "args": [
            "/usr/bin/python3",
            "-m",
            "dangerzone.conversion.doc_to_pixels"
        ],
        "env": [
            "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            "PYTHONPATH=/opt/dangerzone",
            "TERM=xterm"
        ],
        "cwd": "/",
        "capabilities": {
            "bounding": [],
            "effective": [],
            "inheritable": [],
            "permitted": [],
        },
        "rlimits": [
            {
                "type": "RLIMIT_NOFILE",
                "hard": 4096,
                "soft": 4096
            }
        ]
    },
    "root": {
        "path": "rootfs",
        "readonly": true
    },
    "hostname": "dangerzone",
    "mounts": [
        {
            "destination": "/proc",
            "type": "proc",
            "source": "proc"
        },
        {
            "destination": "/dev",
            "type": "tmpfs",
            "source": "tmpfs",
            "options": [
                "nosuid",
                "noexec",
                "nodev"
            ]
        },
        {
            "destination": "/sys",
            "type": "tmpfs",
            "source": "tmpfs",
            "options": [
                "nosuid",
                "noexec",
                "nodev",
                "ro"
            ]
        },
        {
            "destination": "/tmp",
            "type": "tmpfs",
            "source": "tmpfs",
            "options": [
                "nosuid",
                "noexec",
                "nodev"
            ]
        },
        {
            "destination": "/home/dangerzone",
            "type": "tmpfs",
            "source": "tmpfs",
            "options": [
                "nosuid",
                "noexec",
                "nodev"
            ]
        },
        {
            "destination": "/usr/lib/libreoffice/share/extensions/",
            "type": "tmpfs",
            "source": "tmpfs",
            "options": [
                "nosuid",
                "noexec",
                "nodev"
            ]
        }
    ],
    "linux": {
        "namespaces": [
            {
                "type": "pid"
            },
            {
                "type": "network"
            },
            {
                "type": "ipc"
            },
            {
                "type": "uts"
            },
            {
                "type": "mount"
            }
        ]
    }
}

```

## Security considerations

* gVisor does not have an official release on Alpine Linux. The developers
  provide gVisor binaries from a GCS bucket. In order to verify the integrity of
  these binaries, they also provide a SHA-512 hash of the files.
  - If we choose to pin the hash, then we essentially pin gVisor, and we may
    lose security updates.

## Alternatives

gVisor can be integrated with Podman/Docker, but this is the case only on Linux.
Because we want gVisor on Windows and macOS as well, we decided to not move
forward with this approach.
