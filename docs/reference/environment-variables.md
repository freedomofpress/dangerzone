# Environment variables

These variables change how Dangerzone behaves. Most of them exist for development and testing. None of them is needed for normal use.

`DANGERZONE_DEV`
:   Set to `1` to run Dangerzone from a source tree. Resources are looked up under `share/` in the checkout instead of the installed locations, and development-only behaviour is enabled (such as the hidden `--unsafe-dummy-conversion` CLI flag and `QUBES_CONVERSION`). All the [build from source](../how-to/contribute/build-from-source.md#debianubuntu) guides set it.

`DANGERZONE_BYPASS_SIG_CHECKS`
:   Set to `1` to skip the Cosign signature verification of the sandbox image. Meant for testing a locally built, unsigned image stored in `share/container.tar`. See [Use a local container image](../how-to/contribute/build-from-source.md#using-a-local-container-image). Never set this in production.

`DANGERZONE_INSECURE_CONVERTER_PATH`
:   Qubes OS development only. Path to a checkout of the `dangerzone-image` repository (its `src` directory). The server-side conversion code is sent to the disposable qube through the `dz.ConvertDev` RPC call on each conversion, so changes are picked up without rebuilding the RPM. See [Build from source on Qubes OS](../how-to/contribute/build-from-source.md#qubes-os).

`QUBES_CONVERSION`
:   Qubes OS development only, and only honoured together with `DANGERZONE_DEV=1`. Set to `1` to convert documents in disposable qubes instead of containers when running from source inside a qube. Installed Qubes builds detect this on their own.

`SIGSTORE_REKOR_PUBLIC_KEY`
:   Path to a Rekor public key that replaces the one bundled in `share/rekor.pub`, used to verify the transparency log entries of the sandbox image signatures. Only needed if Sigstore rotates its key before a Dangerzone release ships the new one. See [Configure the verification material](../how-to/install/update-the-sandbox.md#configuring-the-verification-material).

## Variables set by Dangerzone

Dangerzone also sets a few variables for the processes it starts. They are listed here so that they are not a surprise:

`OMP_NUM_THREADS`, `OMP_THREAD_LIMIT`
:   Limit the threads used by Tesseract during OCR.

`QT_MAC_WANTS_LAYER`
:   Set on macOS for the Qt graphical toolkit.

`IS_WORKER_PROCESS`
:   Marks the OCR worker processes spawned by the application.
