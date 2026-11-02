# Third-Party Notices

This project may include or interact with third-party software components and
services. The following is a list of attributions for these components and
related technologies:

Please refer to the respective sources for licensing information and further
details regarding the use of these components.

## Binaries and data files

The following components are downloaded and bundled with the Dangerzone
installers. Their exact versions and checksums are tracked in `mazette.lock`.

### Cosign

Code signing and transparency for containers and binaries.

- License: Apache-2.0
- Repository: https://github.com/sigstore/cosign
- Download link: See `cosign` section in `mazette.lock`
- Included in: Dangerzone installers (Windows MSI, macOS DMG, Linux DEB/RPM)

_(Last updated: See date of `mazette.lock`)_

### gvproxy

A new network stack based on gVisor.

- License: Apache-2.0
- Repository: https://github.com/containers/gvisor-tap-vsock
- Download link: See `gvproxy` section in `mazette.lock`
- Included in: Dangerzone installers (macOS DMG)

_(Last updated: See date of `mazette.lock`)_

### Podman

A tool for managing OCI containers and pods.

- License: Apache-2.0
- Repository: https://github.com/containers/podman
- Download link: See `podman` section in `mazette.lock`
- Included in: Dangerzone installers (Windows MSI and macOS DMG)

_(Last updated: See date of `mazette.lock`)_

### Podman Machine OS disk image

Disk images for Podman Machine VMs.

- License: Apache-2.0 (see https://github.com/containers/podman-machine-os/issues/80)
- Repository: https://github.com/containers/podman-machine-os
- Download link: See `machine-os` section in `mazette.lock`
- Included in: Dangerzone installers (Windows MSI and macOS DMG)

_(Last updated: See date of `mazette.lock`)_

### Tesseract data

Fast integer versions of trained LSTM models.

- License: Apache-2.0
- Repository: https://github.com/tesseract-ocr/tessdata_fast/
- Download link: See `tessdata` section in `mazette.lock`
- Included in: Dangerzone installers (Windows MSI and macOS DMG)

_(Last updated: See date of `mazette.lock`)_

### vfkit

Command-line tool to start VMs on macOS.

- License: Apache-2.0
- Repository: https://github.com/crc-org/vfkit
- Download link: See `vfkit` section in `mazette.lock`
- Included in: Dangerzone installers (macOS DMG)

_(Last updated: See date of `mazette.lock`)_

## Python runtime and dependencies

The Windows and macOS installers bundle a Python interpreter, along with the
Python packages that Dangerzone depends on at runtime. On Linux, these packages
are installed from the distribution's repositories instead, with the exception
of PyMuPDF, which is vendored in the Debian package. Their exact versions are
tracked in `poetry.lock`.

Most of these components are distributed under permissive licenses, such as
MIT, BSD, Apache-2.0 and PSF-2.0. Some of them, however, are distributed under
more restrictive licenses, and are listed below.

### PyMuPDF

Python bindings for MuPDF, a library for PDF and other document formats.
Includes the MuPDF library.

- License: AGPL-3.0-only (or a commercial license from Artifex)
- Repository: https://github.com/pymupdf/PyMuPDF
- Included in: Dangerzone installers (Windows MSI, macOS DMG, and Linux DEB)

### PySide6 / Shiboken6

The official Python bindings for the Qt framework. Includes the Qt libraries
(PySide6, PySide6-Essentials, PySide6-Addons and Shiboken6 packages).

- License: LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only (or a commercial
  license from The Qt Company)
- Repository: https://code.qt.io/cgit/pyside/pyside-setup.git
- Included in: Dangerzone installers (Windows MSI and macOS DMG)

_(Last updated: See date of `poetry.lock`)_

## Dangerzone sandbox (container image)

Dangerzone converts documents inside a sandbox, which is a separate container
image that runs isolated from the host. This image is built and distributed
by the [freedomofpress/dangerzone-image](https://github.com/freedomofpress/dangerzone-image)
project, and published at `ghcr.io/freedomofpress/dangerzone/v1`.

The sandbox image includes PyMuPDF and the MuPDF library, which are licensed
under AGPL-3.0. Dangerzone is also licensed under AGPL-3.0. The full source
code of the image, along with the notices for the third-party components it
includes, is available in the dangerzone-image repository.

- License: AGPL-3.0 (PyMuPDF / MuPDF); see the dangerzone-image repository for
  the licenses of the rest of its components
- Repository: https://github.com/freedomofpress/dangerzone-image
- Included in: Dangerzone installers (Windows MSI, macOS DMG) and the
  `dangerzone-full` Linux packages (DEB/RPM), as a bundled image. It can also
  be downloaded or updated with `dangerzone-image upgrade`.
