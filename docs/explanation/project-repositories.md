# The Dangerzone repositories

Dangerzone is more than one repository. The application, the sandbox image
it runs, the packages users install, and the signatures that tie them
together each live in their own place. This page gives contributors the
bird's-eye view: what each repository or site is for, and how they fit
together.

## The big picture

```mermaid
flowchart TB
    REPRO["repro-build<br/><i>reproducible builds</i>"] --> IMG
    IMG["dangerzone-image<br/><i>sandbox image</i>"] -- "monthly and nightly builds" --> GHCR
    SIGNER["ghcr-signer<br/><i>Cosign signatures</i>"] -- "attaches signatures" --> GHCR
    IMG -- "nightly CVE scans" --> CVES["cves.dangerzone.rocks"]
    GHCR[("ghcr.io<br/>signed sandbox image")] -- "bundled in installers,<br/>or downloaded and verified" --> DZ
    DZ["dangerzone<br/><i>application and docs</i>"] -- ".deb and .rpm" --> PKG["packages<br/>packages.freedom.press"]
    DZ -- ".dmg, .msi, source" --> REL["GitHub releases"]
    GHCR & REL -- "download counts" --> STATS["stats.dangerzone.rocks"]
    PKG & REL & GHCR --> USER(["Users"])

    click REPRO "https://github.com/freedomofpress/repro-build" "freedomofpress/repro-build on GitHub"
    click IMG "https://github.com/freedomofpress/dangerzone-image" "freedomofpress/dangerzone-image on GitHub"
    click SIGNER "https://github.com/freedomofpress/ghcr-signer" "freedomofpress/ghcr-signer on GitHub"
    click DZ "https://github.com/freedomofpress/dangerzone" "freedomofpress/dangerzone on GitHub"
    click PKG "https://github.com/freedomofpress/packages" "freedomofpress/packages on GitHub"
    click GHCR "https://github.com/freedomofpress/dangerzone/pkgs/container/dangerzone%2Fv1" "The sandbox image on ghcr.io"
    click REL "https://github.com/freedomofpress/dangerzone/releases" "Dangerzone releases on GitHub"
    click CVES "https://cves.dangerzone.rocks" "Security dashboard"
    click STATS "https://stats.dangerzone.rocks" "Release statistics"
```

Every box in the graph is a link to the repository or site it stands for.

## The repositories

### [freedomofpress/dangerzone](https://github.com/freedomofpress/dangerzone)

The main repository: the desktop application and the `dangerzone-cli`,
`dangerzone-image`, and `dangerzone-machine` tools, written in Python with
Qt. It holds the packaging for every platform (macOS app bundle, Windows
installer, Debian and Fedora packages, Qubes OS integration), the test suite,
the release process, and this documentation site. Releases are tagged here
and their installers are published on the
[GitHub releases page](https://github.com/freedomofpress/dangerzone/releases),
signed with the [release PGP key](../reference/signing-keys.md). This is
where most contributions land, see
[Contribute to Dangerzone](../how-to/contribute.md).

### [freedomofpress/dangerzone-image](https://github.com/freedomofpress/dangerzone-image)

The sandbox: the container image that performs the document-to-pixels
conversion, and the Python package that runs inside it. The image runs under
gVisor and is published on a monthly basis to
`ghcr.io/freedomofpress/dangerzone/v1`, with nightly builds under a testing
namespace. Its CI builds the image reproducibly, attaches provenance
attestations, runs the daily CVE scans, and publishes the security
dashboard. Problems with a document format, a bundled tool, or a CVE inside
the sandbox belong here. The interface between the application and the image
is described in [Sandbox protocol](../reference/sandbox-protocol.md), and the
update mechanism in [Independent sandbox updates](sandbox-updates.md).

### [freedomofpress/packages](https://github.com/freedomofpress/packages)

Artifact storage for the `.deb` and `.rpm` packages served on
[packages.freedom.press](https://packages.freedom.press) (and on
`packages-qa.freedom.press` for release candidates). Release managers send a
pull request with the packages built from a tagged Dangerzone release. Files
are stored with Git LFS and signed with the release key. Only the latest
version is kept, see [Install a previous version](../how-to/install.md#installing-a-previous-version).

### [freedomofpress/ghcr-signer](https://github.com/freedomofpress/ghcr-signer)

Utilities to publish Cosign signatures for the sandbox image to the GitHub
Container Registry without GitHub Personal Access Tokens. Signatures are
prepared offline with the signing key, submitted as a pull request, verified
by CI, and attached to the image by a workflow once merged. The blog post
[The GHCR Signer](https://dangerzone.rocks/news/2026-05-26-ghcr-signer/)
explains why this is needed and how it works. This is the step that lets
Dangerzone [trust a downloaded sandbox image](sandbox-updates.md#why-you-can-trust-a-downloaded-image).

### [freedomofpress/repro-build](https://github.com/freedomofpress/repro-build)

A helper script to build bit-for-bit reproducible container images, by
providing a build environment that is consistent across operating systems and
container engines. `dangerzone-image` uses it so that anyone can rebuild the
sandbox image and compare digests. The blog post
[Reproducing the reproducible images](https://dangerzone.rocks/news/2026-03-02-repro-build/)
tells the story, and [Reproducible builds](reproducible-builds.md) covers
what is reproducible on the Dangerzone side.

## The sites

### [stats.dangerzone.rocks](https://stats.dangerzone.rocks)

Release statistics for the project, generated nightly from the GitHub
releases and the container registry: download counts per release and per
platform, image sizes and digests. Generated by
[freedomofpress/dangerzone-stats](https://github.com/freedomofpress/dangerzone-stats).

### [cves.dangerzone.rocks](https://cves.dangerzone.rocks)

The security dashboard: the results of the nightly
[grype](https://github.com/anchore/grype) scans of the sandbox image, both
for the development branch and the latest released image. This is the
second line of defense described in the [security model](security-model.md).
The dashboard is published from the `dangerzone-image` repository.

### [dangerzone.rocks](https://dangerzone.rocks) and this site

The official website, with the downloads page and the news, is built from
[freedomofpress/dangerzone.rocks](https://github.com/freedomofpress/dangerzone.rocks).
This documentation site is built from the `docs/` directory of the main
repository and published at [docs.dangerzone.rocks](https://docs.dangerzone.rocks).

## How a release flows through them

1. A new sandbox image is built in `dangerzone-image` with `repro-build`,
   pushed to `ghcr.io`, and signed through `ghcr-signer`. Its scans appear on
   `cves.dangerzone.rocks`.
2. A Dangerzone release is tagged in `dangerzone`. Installers bundle the
   signed image. The `.deb` and `.rpm` files go to `packages`, the `.dmg`,
   `.msi`, and source archives go to the GitHub releases page.
3. Users install from `packages.freedom.press` or the releases page. Between
   releases, Dangerzone fetches new signed images from `ghcr.io`, and the
   download counts show up on `stats.dangerzone.rocks`.

The step-by-step version of this is the [release process](../how-to/release/index.md).
