# Developer scripts

This directory holds some scripts that are helpful for developing on Dangerzone.
Read below for more details on these scripts.

## Create Dangerzone environments (`env.py`)

This script creates environments where a user can run Dangerzone, allows the
user to run arbitrary commands in these environments, as well as run Dangerzone
(nested containerization).

It supports two types of environments:

1. Dev environment. This environment has developer tools, necessary for
   Dangerzone, baked in. Also, it mounts the Dangerzone source under
   `/home/user/dangerzone` in the container. The developer can then run
   Dangerzone from source, with `poetry run ./dev_scripts/dangerzone`.
2. End-user environment. This environment has only Dangerzone installed in it,
   from the .deb/.rpm package that we have created. For convenience, it also has
   the Dangerzone source mounted under `/home/user/dangerzone`, but it lacks
   Poetry and other build tools. The developer can run Dangerzone there with
   `dangerzone`. This environment is the most vanilla Dangerzone environment,
   and should be closer to the end user's environment, than the development
   environment.

Each environment corresponds to a Dockerfile, which is generated on the fly. The
developer can see this Dockerfile by passing `--show-dockerfile`.

For usage information, run `./dev_scripts/env.py --help`.

### Nested containerization

Since the Dangerzone environments are containers, this means that the Podman
containers that Dangerzone creates have to be nested containers. This has some
challenges that we will highlight below:

1. Containers typically only have a subset of syscalls allowed, and sometimes
   only for specific arguments. This happens with the use of
   [seccomp filters](https://docs.docker.com/engine/security/seccomp/). For
   instance, in Docker, the `clone` syscall is limited in containers and cannot
   create new namespaces
   (https://docs.docker.com/engine/security/seccomp/#significant-syscalls-blocked-by-the-default-profile). For testing/development purposes, we can get around this limitation
   by disabling the seccomp filters for the external container with
   `--security-opt seccomp=unconfined`. This has the same effect as developing
   Dangerzone locally, so it should probably be sufficient for now.

2. While Linux supports nested namespaces, we need extra handling for nested
   user namespaces. By default, the configuration for each user namespace (see
   [`man login.defs`](https://man7.org/linux/man-pages/man5/login.defs.5.html)
   is to reserve 65536 UIDs/GIDs, starting from UID/GID 100000. This works fine
   for the first container, but can't work for the nested container, since it
   doesn't have enough UIDs/GIDs to refer to UID 100000. Our solution to this is
   to restrict the number of UIDs/GIDs allowed in the nested container to 2000,
   which should be enough to run `podman` in it.

3. Containers also restrict the capabilities (see
   [`man capabilities`](https://man7.org/linux/man-pages/man7/capabilities.7.html))
   of the processes that run in them. By default, containers do not have mount
   capabilities, since it requires `CAP_SYS_ADMIN`, which effectively
   [makes the process root](https://lwn.net/Articles/486306/) in the specific
   user namespace. In our case, we have to give the Dangerzone environment this
   capability, since it will have to mount directories in Podman containers. For
   this reason, as well as some extra things we bumped into during development,
   we pass `--privileged` when creating the Dangerzone environment, which
   includes the `CAP_SYS_ADMIN` capability.

### GUI containerization

Running a GUI app in a container is a tricky subject for multi-platform apps. In
our case, we deal specifically with Linux environments, so we can target just
this platform.

To understand how a GUI app can draw in the user's screen from within a
container, we must first understand how it does so outside the container. In
Unix-like systems, GUI apps act like
[clients to a display server](https://wayland.freedesktop.org/architecture.html).
The most common display server implementation is X11, and the runner-up is
Wayland. Both of these display servers share some common traits, mainly that
they use Unix domain sockets as a way of letting clients communicate with them.

So, this gives us the answer on how one can run a containerized GUI app; they
can simply mount the Unix Domain Socket in the container. In practice this is
more nuanced, for two reasons:

1. Wayland support is not that mature on Linux, so we need to
   [set some extra environment variables](https://github.com/mviereck/x11docker/wiki/How-to-provide-Wayland-socket-to-docker-container). To simplify things, we will target
   X11 / XWayland hosts, which are the majority of the Linux OSes out there.
2. Sharing the Unix Domain socket does not allow the client to talk to the
   display server, for security reasons. In order to allow the client, we need
   to mount a magic cookie stored in a file pointed at by the `$XAUTHORITY`
   envvar. Else, we can use `xhost`, which is considered slightly more dangerous
   for multi-user environments.

### Caching and Reproducibility

In order to build Dangerzone environments, the script uses the following inputs:

* Dev environment:
  - Distro name and version. Together, these comprise the base container image.
  - `poetry.lock` and `pyproject.toml`. Together, these comprise the build
    context.
* End-user environment:
  - Distro name and version. Together, these comprise the base container image.
  - `.deb` / `.rpm` Dangerzone package, as found under `deb_dist/` or `dist/`
    respectively.

Any change in these inputs busts the cache for the corresponding image. In
theory, this means that the Dangerzone environment for each commit can be built
reproducibly. In practice, there are some issues that we haven't covered yet:

1. The output images are:
   * Dev: `dangerzone.rocks/build/{distro_name}:{distro_version}`
   * End-user: `dangerzone.rocks/{distro_name}:{distro_version}`

   These images do not contain the commit/version of the Dangerzone source they
   got created from, so each one overrides the other.
2. The end-user environment expects a `.deb.` / `.rpm` tagged with the version
   of Dangerzone, but it doesn't insist being built from the current Dangerzone
   commit. This means that stale packages may be installed in the end-user
   environment.
3. The base images may be different in various environments, depending on when
   they where pulled.

### State

The main goal behind these Dangerzone environments is to make them immutable,
so that they do not require to be stored somewhere, but can be recreated from
their images. Any change to these environments should therefore be reflected to
their Dockerfile.

To enforce immutability, we delete the containers every time we run a command or
an interactive shell exits. This means that these environments are suitable only
for running Dangerzone commands, and not doing actual development in them
(install an editor, configure bash prompts, etc.)

The only point where we allow mutability is the directory where Podman stores
the images and stopped containers, which may be useful for developers. If this
proves to be an issue, we will reconsider.

## Run QA (`qa.py`)

This script runs the QA steps for a supported platform, in order to make sure
that the dev does not skip something. These steps are taken from our [release
instructions](../RELEASE.md#qa).

The idea behind this script is that it will present each step to the user and
ask them to perform it manually and specify it passes, in order to continue to
the next one. For specific steps, it allows the user to run them automatically.
In steps that require a Dangerzone dev environment, this script uses the
`env.py` script to create one.

Including all the supported platforms in this script is still a work in
progress.
