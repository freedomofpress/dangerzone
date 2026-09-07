# Sandbox protocol

This page describes the interface between Dangerzone (the host) and the
sandbox that converts a document to pixels. It is the "API" of the container
image. The image and the conversion code it runs are maintained in the
[dangerzone-image](https://github.com/freedomofpress/dangerzone-image)
repository. The host side lives in `dangerzone/isolation_provider/`.

## Invocation

For each document, Dangerzone starts one container from the sandbox image
and runs:

```
/usr/bin/python3 -m dangerzone.conversion.doc_to_pixels
```

On Qubes OS with the native integration, the equivalent is the `dz.Convert`
RPC call to a disposable qube (and `dz.ConvertDev` during development).

The container is started with these flags, in addition to the image digest
pinned after signature verification:

| Flag | Purpose |
| ---- | ------- |
| `--network=none` | No network access |
| `--cap-drop all --cap-add SYS_CHROOT` | Drop every capability except the one gVisor needs to set up its root |
| `--security-opt no-new-privileges` | No privilege escalation |
| `--security-opt seccomp=<profile>` | Bundled seccomp profile that allows gVisor to run (`share/seccomp.gvisor.json`), since default profiles may block `ptrace(2)` |
| `--userns nomap` | Do not map the host user into the container (Podman 4.1 and later) |
| `--security-opt label=type:container_engine_t` | SELinux label that lets a container engine run nested, on hosts that use SELinux |
| `-u dangerzone` | Run as the unprivileged `dangerzone` user inside the container |
| `--log-driver none` | Do not keep container logs |
| `--rm` | Remove the container when it exits |
| `-i` | Keep standard input open |
| `-e RUNSC_DEBUG=1` | Only with `--debug`: make gVisor log verbosely |

Inside the container, the conversion runs under gVisor (`runsc`).

## Input

The host writes the raw bytes of the untrusted document to the container's
standard input, then closes it. No filename, format, or options are sent: the
sandbox detects the format itself.

## Output

The container writes a binary stream to standard output. All integers are
2-byte unsigned big-endian values (`INT_BYTES = 2`).

```
n_pages                      uint16
repeat n_pages times:
    width                    uint16
    height                   uint16
    pixels                   width * height * 3 bytes, RGB, row-major
```

Pages are rendered at `DEFAULT_DPI = 150` pixels per inch.

The host validates every value before using it:

| Value | Accepted range | Error otherwise |
| ----- | -------------- | --------------- |
| `n_pages` | `1` to `MAX_PAGES` (`10000`) | `MaxPagesException` |
| `width` | `1` to `MAX_PAGE_WIDTH` (`10000`) | `MaxPageWidthException` |
| `height` | `1` to `MAX_PAGE_HEIGHT` (`10000`) | `MaxPageHeightException` |

A short read (fewer bytes than announced) raises `ConverterProcException`.
After the last page, the host closes standard output and ignores anything
else. Each page's pixels are turned into a PDF page on the host (with OCR if
requested) as soon as they arrive, so memory use does not grow with the
document size.

## Standard error

Standard error carries the sandbox's own diagnostics. It is only shown with
`--debug`, after sanitization of control characters.

## Exit codes

The container communicates failures through its exit code. Codes below 128
are treated as unexpected errors. Conversion errors start at
`ERROR_SHIFT = 128`:

| Exit code | Meaning |
| --------- | ------- |
| 128 | Unspecified conversion error |
| 138 | The document format is not supported |
| 144 | HWP / HWPX formats are not supported in Qubes |
| 148 | Conversion to PDF with LibreOffice failed |
| 158 | The document appears to be corrupted and could not be opened |
| 168 | Page-related error (generic) |
| 169 | Number of pages could not be extracted from PDF |
| 170 | Number of pages exceeds maximum |
| 172 | A page exceeded the maximum width |
| 173 | A page exceeded the maximum height |
| 174 | Page count mismatch between the document and the rendered pages |
| 228 | Some unexpected error occurred while converting the document |
| 126 | Qubes OS only: the qrexec call failed |

Any other code maps to "Unknown error code". The host-side definitions are
in `dangerzone/conversion_errors.py`.

## Versioning

The image is published as `ghcr.io/freedomofpress/dangerzone/v1`. The `v1`
suffix is the protocol version: a change that breaks this interface will be
published under `v2`, and a Dangerzone release will switch to it. See
[Independent sandbox updates](../explanation/sandbox-updates.md).
