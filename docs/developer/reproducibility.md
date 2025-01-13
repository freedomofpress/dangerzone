# Reproducible builds

We want to improve the transparency and auditability of our build artifacts, and
a way to achieve this is via reproducible builds. For a broader understanding of
what reproducible builds entail, check out https://reproducible-builds.org/.

Our build artifacts consist of:
* Container images (`amd64` and `arm64` architectures)
* macOS installers (for Intel and Apple Silicon CPUs)
* Windows installer
* Fedora packages (for regular Fedora distros and Qubes)
* Debian packages (for Debian and Ubuntu)

As of writing this, only the following artifacts are reproducible:
* Container images (see [#1047](https://github.com/freedomofpress/dangerzone/issues/1047))

In the following sections, we'll mention some specifics about enforcing
reproducibility for each artifact type.

## Container image

### Updating the image

The fact that our image is reproducible also means that it's frozen in time.
This means that rebuilding the image without updating our Dockerfile will
**not** receive security updates.

Here are the necessary variables that make up our image in the `Dockerfile.env`
file:
* `DEBIAN_IMAGE_DATE`: The date that the Debian container image was released
* `DEBIAN_ARCHIVE_DATE`: The Debian snapshot repo that we want to use
* `GVISOR_ARCHIVE_DATE`: The gVisor APT repo that we want to use
* `H2ORESTART_CHECKSUM`: The SHA-256 checksum of the H2ORestart plugin
* `H2ORESTART_VERSION`: The version of the H2ORestart plugin

If you update these values in `Dockerfile.env`, you must also create a new
Dockerfile with:

```
make Dockerfile
```

Updating `Dockerfile` without bumping `Dockerfile.in` is detected and should
trigger a CI error.

### Reproducing the image

For a simple way to reproduce a Dangerzone container image, you can checkout the
commit this image was built from (you can find it from the image tag in its
`g<commit>` portion), and run the following command in a Linux environment:

```
./dev_scripts/reproduce-image.py --source <image>
```

This command will download the `diffoci` helper, build a container image from
the current Git commit, and ensure that the built image matches the source one,
with the exception of image names and file timestamps.

> [!TIP]
> If the source image is not pushed to a registry, and is local instead, you
> can prefix it with `docker://` or `podman://` accordingly, so that `diffoci`
> can load it from the local Docker / Podman container engine. For example:
>
> ```
> ./dev_scripts/reproduce.py --source podman://dangerzone.rocks/dangerzone:0.8.0-125-g725ce3b
> ```
