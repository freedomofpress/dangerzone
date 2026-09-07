# How Dangerzone works

Dangerzone takes potentially dangerous PDFs, office documents, or images and
converts them to a safe PDF. This page explains what "safe" means here and
how the conversion achieves it.

## The core idea: documents in, pixels out

A document format like PDF or DOCX is a small program as much as it is a
picture of a page. It can carry scripts, links, embedded files, fonts with
their own bytecode, and structures that exercise obscure corners of whichever
parser opens them. A malicious document is one crafted so that opening it
triggers a bug in the viewer and runs the attacker's code on your machine.

Dangerzone sidesteps the problem instead of trying to detect malice. You give
it a document that you don't know if you can trust (for example, an email
attachment). Inside of a sandbox, Dangerzone converts the document to a PDF
(if it isn't already one), and then converts the PDF into raw pixel data: a
huge list of RGB color values for each page. Then, outside of the sandbox,
Dangerzone takes this pixel data and converts it back into a PDF.

The pixel data is the trick. A grid of colour values can't contain a script or
a malformed object. Whatever the original document was hiding, it doesn't
survive being rendered to a bitmap. The safe PDF is rebuilt from those bitmaps
by trusted code on your side of the fence, so its structure is entirely
Dangerzone's own.

Dangerzone was inspired by
[Qubes trusted PDF](https://blog.invisiblethings.org/2013/02/21/converting-untrusted-pdfs-into-trusted.html),
which applies the same idea with virtual machines. Dangerzone brings it to
non-Qubes operating systems by using containers as sandboxes.

## The pipeline

1. **Selection.** You pick one or more documents in the graphical
   application, or pass them to `dangerzone-cli`. The document formats
   Dangerzone accepts are listed in [supported formats](../reference/supported-formats.md).
2. **Document to PDF, in the sandbox.** Dangerzone starts a sandbox and streams
   the untrusted document into it. Office documents are converted to PDF with
   LibreOffice. Images and PDFs skip this step or go through PyMuPDF.
3. **PDF to pixels, in the sandbox.** Each page is rendered to raw RGB pixels
   with PyMuPDF and streamed back out of the sandbox, page by page, with the
   page dimensions.
4. **Pixels to PDF, on the host.** Outside the sandbox, Dangerzone assembles
   the pages into a new PDF, optionally runs OCR with Tesseract to add a text
   layer, and compresses the result.
5. **Delivery.** The safe PDF is saved with a `-safe.pdf` suffix, the original
   is optionally moved to an `unsafe/` directory, and the safe PDF is
   optionally opened in your PDF viewer.

Only step 4 handles data as anything richer than pixels, and step 4 only ever
sees pixels. The tools with the large attack surface, LibreOffice and the PDF
renderer, only run inside the sandbox in steps 2 and 3.

## The sandbox

The sandbox is a container image, built and published separately in the
[dangerzone-image](https://github.com/freedomofpress/dangerzone-image)
repository. Dangerzone runs it with Podman:

* On Linux, with the system's Podman.
* On macOS and Windows, with a Podman that is embedded in the application and
  runs inside a small Linux virtual machine (a "Podman machine"). On Windows,
  that machine is a WSL distribution.

The container has no network access, so if a malicious document compromises
it, it can't phone home. Inside the container, the conversion runs under
[gVisor](https://gvisor.dev/), an application kernel written in Go that
implements a substantial portion of the Linux system call interface. gVisor
sits between the conversion tools and the real kernel: an exploit that takes
over LibreOffice still has to break out of gVisor, then out of the container,
before it reaches your system. We wrote about this design in a
[blog post](https://dangerzone.rocks/news/2024-09-23-gvisor/).

The image is signed with Cosign and updated independently from Dangerzone,
so that vulnerabilities in the tools inside it can be patched quickly. See
[Independent sandbox updates](sandbox-updates.md).

## Qubes OS

On Qubes OS, Dangerzone can use disposable qubes instead of containers, which
is closer to the original Qubes trusted PDF design. The conversion runs in an
offline disposable qube (`dz-dvm`) that is created for the conversion and
destroyed afterwards. Communication happens over Qubes RPC (`dz.Convert`),
and only pixels come back. This integration is in beta, see
[Qubes OS integration](qubes-integration.md) and the
[installation instructions](../how-to/install.md#qubes-os).

## What you give up

Because the safe PDF is rebuilt from pixels:

* Links, forms, bookmarks, and embedded files are gone.
* Text is only searchable and selectable if you enable OCR, and OCR is never
  perfect.
* The safe PDF is often larger than the original, even after compression,
  since every page is an image.
* Metadata is destroyed. For Dangerzone this is a feature: metadata is one of
  the two things it promises to remove. See [Security model](security-model.md).

For a document you receive from someone you don't trust, these are usually
good trades.
