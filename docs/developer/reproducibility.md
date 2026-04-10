# Reproducible builds

We want to improve the transparency and auditability of our build artifacts, and
a way to achieve this is via reproducible builds. For a broader understanding of
what reproducible builds entail, check out https://reproducible-builds.org/.

Our build artifacts consist of:

- Container images (`amd64` and `arm64` architectures)
- macOS installers (for Intel and Apple Silicon CPUs)
- Windows installer
- Fedora packages (for regular Fedora distros and Qubes)
- Debian packages (for Debian and Ubuntu)

As of writing this, only the following artifacts are reproducible:

- Container images (see [#1047](https://github.com/freedomofpress/dangerzone/issues/1047)). You can find a detailed documentation on reproducible containers in the [dangerzone-image repository](https://github.com/freedomofpress/dangerzone-image).