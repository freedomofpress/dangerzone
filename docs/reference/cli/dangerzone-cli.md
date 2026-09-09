# dangerzone-cli

`dangerzone-cli` converts one or more documents into safe PDFs from a terminal. It uses the same conversion pipeline and the same sandbox as the graphical application. For a guided introduction, see [Convert documents from the command line](../../tutorials/convert-from-the-command-line.md).

## Location

| Platform | Command |
| -------- | ------- |
| Linux | `dangerzone-cli` |
| macOS | `/Applications/Dangerzone.app/Contents/MacOS/dangerzone-cli` |
| Windows | `C:\Program Files\Dangerzone\dangerzone-cli.exe` |
| Source tree | `poetry run dangerzone-cli` |

## Usage

The output below is generated from the code at the time the documentation was built, so it matches the installed version of the same release.

<!-- [[[cog
from docs_cog import cli_help
cli_help("dangerzone-cli")
]]] -->
```console
$ dangerzone-cli --help
Usage: dangerzone-cli [OPTIONS] [FILENAMES]...

Options:
  --output-filename TEXT        Default is filename ending with -safe.pdf
  --ocr-lang TEXT               Language to OCR, defaults to none
  --archive                     Archives the unsafe version in a subdirectory
                                named 'unsafe'
  --debug                       Run Dangerzone in debug mode, to get logs from
                                gVisor.
  --set-container-runtime TEXT  The name or full path of the container runtime
                                you want Dangerzone to use. You can specify the
                                value 'default' if you want to take back your
                                choice, and let Dangerzone use the default
                                runtime for this OS
  --linger                      Do not stop the Podman machine VM that
                                Dangerzone uses to run containers, after the
                                conversions have completed. This is useful if
                                you want to run multiple conversions in a row,
                                since the startup of the VM takes some time. If
                                you choose to let the Podman machine linger, you
                                will need to stop it manually with `dangerzone-
                                machine stop`. This option affects only
                                Windows/macOS platforms.
  --version                     Show the version and exit.
  --help                        Show this message and exit.
```
<!-- [[[end]]] -->

`FILENAMES...` are the documents to convert. Every file must exist and must have one of the [supported formats](../supported-formats.md). Conversions run sequentially, in the given order. `--output-filename` is only valid with a single input file, and the name must end with `.pdf`. `--set-container-runtime` stores the choice in the [settings file](../settings.md) and exits without converting anything, see [Using Podman Desktop](../../how-to/install/use-podman-desktop.md).

## Behaviour

On start, the tool prints a banner and then, when needed, installs the Windows Subsystem for Linux, stops other Podman machines, initializes and starts the Dangerzone Podman machine, checks for updates, and installs the sandbox image. On Linux, none of the machine steps apply. On Qubes OS with the native integration, conversions run in disposable qubes.

!!! note "Slim Linux packages"

    On Linux, the `dangerzone` package doesn't come with the sandbox bundled, and so the CLI does not download the sandbox on its own.
   
    Initialize it with `dangerzone-image upgrade`, or start the graphical application and accept the download. Alternatively, the `dangerzone-full` package bundles the sandbox.

Progress for each stage of each document is printed to the terminal. A failed conversion reports the error and moves on to the next document.

## Exit status

`0`
:   All conversions succeeded (or the runtime was set with
    `--set-container-runtime`).

`1`
:   A usage error, an invalid OCR language, or at least one failed
    conversion.

## Environment

`DANGERZONE_DEV`, `DANGERZONE_BYPASS_SIG_CHECKS`, `QUBES_CONVERSION` and the other variables listed in [environment variables](../environment-variables.md) affect this tool.

## Examples

Convert a single PDF next to itself:

```console
$ dangerzone-cli report.pdf
```

Convert several office documents with English OCR and archive the originals:

```console
$ dangerzone-cli --ocr-lang eng --archive *.docx *.pptx
```

Choose the output name:

```console
$ dangerzone-cli --output-filename ~/clean/report.pdf report.pdf
```

Point Dangerzone at Podman Desktop on macOS, then revert:

```console
$ /Applications/Dangerzone.app/Contents/MacOS/dangerzone-cli --set-container-runtime /opt/podman/bin/podman
$ /Applications/Dangerzone.app/Contents/MacOS/dangerzone-cli --set-container-runtime default
```
