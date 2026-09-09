# dangerzone-image

`dangerzone-image` manages the sandbox container image that Dangerzone uses to convert documents: it fetches updates, verifies signatures, and prepares or loads archives for air-gapped machines. For step-by-step usage, see [Independent Container Updates](../../how-to/install/update-the-sandbox.md). For the design, see [Independent sandbox updates](../../explanation/sandbox-updates.md).

## Location

| Platform | Command |
| -------- | ------- |
| Linux | `dangerzone-image` |
| macOS | `/Applications/Dangerzone.app/Contents/MacOS/dangerzone-image` |
| Windows | `C:\Program Files\Dangerzone\dangerzone-image.exe` |
| Source tree | `poetry run dangerzone-image` |

## Usage

The output below is generated from the code at the time the documentation was built, so it matches the installed version of the same release.

<!-- [[[cog
from docs_cog import cli_help
cli_help("dangerzone-image")
]]] -->
```console
$ dangerzone-image --help
Usage: dangerzone-image [OPTIONS] COMMAND [ARGS]...

Options:
  --debug
  --help   Show this message and exit.

Commands:
  load-archive      Use ARCHIVE_FILENAME as the dangerzone sandbox image
  prepare-archive   Prepare an archive to upgrade the dangerzone image...
  store-signatures  Retrieves and stores the signatures of the remote sandbox
  upgrade           Upgrade the sandbox to the latest version available.
  verify-local      Ensures local image signature(s) match the embedded...
```
<!-- [[[end]]] -->

## Commands

### `upgrade`

<!-- [[[cog
from docs_cog import cli_help
cli_help("dangerzone-image", "upgrade")
]]] -->
```console
$ dangerzone-image upgrade --help
Usage: dangerzone-image upgrade [OPTIONS]

  Upgrade the sandbox to the latest version available.

  To upgrade to a custom sandbox image, use "prepare-archive" and "load-archive"
  instead.

Options:
  --help  Show this message and exit.
```
<!-- [[[end]]] -->

The tool resolves the digest of the default image in the registry, downloads it, verifies its Cosign signatures against the bundled public key, and stores the signatures locally. If the local image is already up to date, it says so and exits successfully. Requires a working container runtime.

### `verify-local`

<!-- [[[cog
from docs_cog import cli_help
cli_help("dangerzone-image", "verify-local")
]]] -->
```console
$ dangerzone-image verify-local --help
Usage: dangerzone-image verify-local [OPTIONS]

  Ensures local image signature(s) match the embedded public key.

Options:
  --image TEXT  The name of the image to check signatures for  [default:
                ghcr.io/freedomofpress/dangerzone/v1]
  --help        Show this message and exit.
```
<!-- [[[end]]] -->

Requires a working container runtime.

### `prepare-archive`

<!-- [[[cog
from docs_cog import cli_help
cli_help("dangerzone-image", "prepare-archive")
]]] -->
```console
$ dangerzone-image prepare-archive --help
Usage: dangerzone-image prepare-archive [OPTIONS]

  Prepare an archive to upgrade the dangerzone image (useful for airgapped
  environment)

Options:
  --image TEXT   The sandbox container registry location  [default:
                 ghcr.io/freedomofpress/dangerzone/v1]
  --output TEXT  The location of the generated archive. '{arch}' will be
                 replaced by the specified or detected architecture (see --arch)
                 [default: dangerzone-{arch}.tar]
  --arch TEXT    The architecture to prepare the archive for.  [default: (the
                 architecture of the current machine)]
  --help         Show this message and exit.
```
<!-- [[[end]]] -->

The archive contains the image, its signatures, and a `dangerzone.json` manifest, so that the receiving machine can verify it without network access. A digest can be pinned with `--image name@sha256:...`. `--arch` accepts `amd64` or `arm64`. This command does not need a container runtime.

### `load-archive`

<!-- [[[cog
from docs_cog import cli_help
cli_help("dangerzone-image", "load-archive")
]]] -->
```console
$ dangerzone-image load-archive --help
Usage: dangerzone-image load-archive [OPTIONS] ARCHIVE_FILENAME

  Use ARCHIVE_FILENAME as the dangerzone sandbox image

Options:
  --force  Force the installation, bypassing logindex verification checks
  --help   Show this message and exit.
```
<!-- [[[end]]] -->

The signatures in the archive are verified before the image is loaded, and the tool refuses to install an image older than the currently installed one unless `--force` is given. Requires a working container runtime.

### `store-signatures`

<!-- [[[cog
from docs_cog import cli_help
cli_help("dangerzone-image", "store-signatures")
]]] -->
```console
$ dangerzone-image store-signatures --help
Usage: dangerzone-image store-signatures [OPTIONS]

  Retrieves and stores the signatures of the remote sandbox

Options:
  --image TEXT  [default: ghcr.io/freedomofpress/dangerzone/v1]
  --help        Show this message and exit.
```
<!-- [[[end]]] -->

Fetches and stores the signatures without pulling the image itself.

## Exit status

Commands print a ✅ line on success and exit with `0`. On failure they print a ❌ line and abort with a non-zero status. Typical failures are signature verification errors and an archive older than the installed image.

## Environment

`SIGSTORE_REKOR_PUBLIC_KEY` overrides the bundled Rekor public key, and `DANGERZONE_BYPASS_SIG_CHECKS` disables signature verification for local testing. See [environment variables](../environment-variables.md).

## Examples

Fetch the latest sandbox:

```console
$ dangerzone-image upgrade
✅ The local image ghcr.io/freedomofpress/dangerzone/v1 has been upgraded
✅ The image has been signed with /usr/share/dangerzone/freedomofpress-dangerzone.pub
✅ Signatures have been verified and stored locally
```

Prepare an archive for an air-gapped `amd64` machine, then load it there:

```console
$ dangerzone-image prepare-archive --arch amd64
✅ Archive dangerzone-amd64.tar created
$ dangerzone-image load-archive dangerzone-amd64.tar
✅ Installed image dangerzone-amd64.tar on the system as ghcr.io/freedomofpress/dangerzone/v1 with digest sha256:…
```
