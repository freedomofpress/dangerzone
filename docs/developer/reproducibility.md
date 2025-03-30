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
* `DEBIAN_IMAGE_DIGEST`: The index digest for the Debian container image
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
`g<commit>` portion), retrieve the date it was built (also included in the image
tag), and run the following command in any environment:

```
./dev_scripts/reproduce-image.py \
    --debian-archive-date <date> \
    <digest>
```

where:
* `<date>` should be given in YYYYMMDD format, e.g, 20250226
* `<digest>` is the SHA-256 hash of the image for the **current platform**, with
  or without the `sha256:` prefix.

This command will build a container image from the current Git commit and the
provided date for the Debian archives. Then, it will compare the digest of the
manifest against the provided one. This is a simple way to ensure that the
created image is bit-for-bit reproducible.
