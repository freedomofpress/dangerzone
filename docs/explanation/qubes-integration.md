# Qubes OS integration

On Qubes OS, Dangerzone can run without containers: the conversion happens in a disposable qube, which is what Qubes OS is built for. This page explains how that integration is put together. The installation steps are in [Installation](../how-to/install/index.md#qubes-os), the development setup in [Development environment](../how-to/contribute/build-from-source.md#qubes-os). The integration is in [beta](https://github.com/freedomofpress/dangerzone/issues/413).

The conversion runs in a disposable qube created from an offline template (`dz-dvm`), through Qubes RPC. Here, no container images are used at all, and update checks are skipped.

It is also possible to select the Qubes converter by setting the `QUBES_CONVERSION=1` environment variable.

## What happens during a conversion

1. The application calls `qrexec-client-vm @dispvm:dz-dvm dz.Convert`. Qubes OS starts a fresh disposable qube from `dz-dvm`, provided the RPC policy in `/etc/qubes/policy.d/50-dangerzone.policy` allows it.
2. The untrusted document is written to the RPC call's standard input. The `dz.Convert` service in the disposable qube runs the same document-to-pixels code that the container image runs, and writes the page count, page sizes, and RGB pixels to standard output. See the [sandbox protocol](../reference/sandbox-protocol.md) for more details on this.
3. The application rebuilds the PDF from the pixels in the app qube, exactly as on other platforms.
4. The disposable qube is destroyed when the call ends.

Because `dz-dvm` has no network (`netvm=""`) and cannot spawn further disposables (`default_dispvm=''`), a compromised converter is stuck in a qube that disappears. The second setting is the one the [2023-10-25 advisory](../advisories/2023-10-25.md) added.

## What the package contains

The `dangerzone-qubes` RPM is built from the same source with `./install/linux/build-rpm.py --qubes`. Compared with the regular package it ships the RPC services under `/etc/qubes-rpc/` and depends on the server-side conversion package (`dangerzone-insecure-converter-qubes`) and LibreOffice, so that the template has everything the disposable qube needs.

## Development: `dz.ConvertDev`

Rebuilding and installing the RPM in the template for every change to the converter is not very practical. In development (`DANGERZONE_DEV=1`), Dangerzone calls `dz.ConvertDev` instead, and first sends a zip of the converter's Python sources (from `DANGERZONE_INSECURE_CONVERTER_PATH`) over the RPC channel. The disposable qube unpacks and runs that code, so changes to the converter are picked up immediately. The RPC policy for development allows both `dz.Convert` and `dz.ConvertDev`.

## Limitations

* Hancom HWP files are [not supported on Qubes OS](https://github.com/freedomofpress/dangerzone/issues/494).
* Support is manual QA only on the latest Fedora template, see [Operating System support](../reference/supported-platforms.md).
* The startup errors Dangerzone shows for a missing `dz-dvm`, a missing policy, or a qube that can't start are part of the [QA scenarios](../how-to/release/qa.md#9-dangerzone-shows-helpful-errors-for-setup-issues-on-qubes).
