# How-to guides

How-to guides are recipes. Each one takes you through the steps needed to reach
a specific goal, and assumes you already know the basics. They don't teach and
they don't explain: for those, look at the [tutorials](../tutorials/index.md)
and the [explanation](../explanation/index.md) section.

## Install and update

* [Installation](install.md) for each platform:
  [macOS](install.md#macos), [Windows](install.md#windows),
  [Ubuntu Linux](install.md#ubuntu-debian), [Debian Linux](install.md#ubuntu-debian),
  [Fedora Linux](install.md#fedora), [Qubes OS (beta)](install.md#qubes-os),
  and [Tails](install.md#tails), including
  [Homebrew](install.md#macos) and [Winget](install.md#windows), and
  [a previous version](install.md#installing-a-previous-version).
  You can read more about our operating system support
  [here](../reference/supported-platforms.md).
* [Verifying PGP signatures](verify-pgp-signatures.md) of downloaded
  installers and packages.
* [Update Dangerzone](update-dangerzone.md) to the latest release.
* [Independent Container Updates](update-the-sandbox.md): update the sandbox
  image, verify it locally, check its build attestations, or install it on an
  air-gapped machine.
* [Using Podman Desktop](use-podman-desktop.md) or another custom runtime.

## Contribute

* [Report an issue](report-an-issue.md): what to include in a bug report, and
  where security reports go instead.
* [Contribute to Dangerzone](contribute.md): from finding an issue to a
  merged pull request.
* Set up a [development environment](build-from-source.md) on
  [Debian/Ubuntu](build-from-source.md#debianubuntu),
  [Fedora](build-from-source.md#fedora),
  [Qubes OS](build-from-source.md#qubes-os),
  [macOS](build-from-source.md#macos), or
  [Windows](build-from-source.md#windows), and
  [use a local container image](build-from-source.md#using-a-local-container-image).
* [Run the tests](run-the-tests.md).
* [Use the containerized dev environments](dev-environments.md) to run
  Dangerzone on any supported Linux distribution.
* [Debug the sandbox](debug-the-sandbox.md): gVisor logs and a shell inside
  the image.

## Release

* [Release a new version](release/index.md): pre-release tasks, build
  environments, artifacts, QA, and publication.
* [Managing Python installations](manage-python-installations.md) on the
  macOS and Windows build machines.
* [Using the Doit Automation Tool](build-with-doit.md) to build release
  artifacts.
* [Verifying reproducible builds](../explanation/reproducible-builds.md#verifying-reproducibility)
  of the Debian packages.
