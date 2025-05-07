## QA

To ensure that new releases do not introduce regressions, and support existing
and newer platforms, we have to test that the produced packages work as expected.

Check the following:

- [ ] Make sure that the tip of the `main` branch passes the CI tests.
- [ ] Make sure that the Apple account has a valid application password and has
      agreed to the latest Apple terms (see [macOS release](#macos-release)
      section).

Because it is repetitive, we wrote a script to help with the QA.
It can run the tasks for you, pausing when it needs manual intervention.

You can run it with a command like:

```bash
poetry run ./dev_scripts/qa.py {distro}-{version}
```

### The checklist

- [ ] Create a test build in Windows and make sure it works:
  - [ ] Check if the suggested Python version is still supported.
  - [ ] Create a new development environment with Poetry.
  - [ ] Build the container image and ensure the development environment uses
    the new image.
  - [ ] Download the necessary assets using `./dev_scripts/inventory.py sync`
  - [ ] Run the Dangerzone tests.
  - [ ] Build and run the Dangerzone .exe
  - [ ] Test some QA scenarios (see [Scenarios](#Scenarios) below).
- [ ] Create a test build in macOS (Intel CPU) and make sure it works:
  - [ ] Check if the suggested Python version is still supported.
  - [ ] Create a new development environment with Poetry.
  - [ ] Build the container image and ensure the development environment uses
    the new image.
  - [ ] Download the necessary assets using `./dev_scripts/inventory.py sync`
  - [ ] Run the Dangerzone tests.
  - [ ] Create and run an app bundle.
  - [ ] Test some QA scenarios (see [Scenarios](#Scenarios) below).
- [ ] Create a test build in macOS (M1/2 CPU) and make sure it works:
  - [ ] Check if the suggested Python version is still supported.
  - [ ] Create a new development environment with Poetry.
  - [ ] Build the container image and ensure the development environment uses
    the new image.
  - [ ] Download the necessary assets using `./dev_scripts/inventory.py sync`
  - [ ] Run the Dangerzone tests.
  - [ ] Create and run an app bundle.
  - [ ] Test some QA scenarios (see [Scenarios](#Scenarios) below).
- [ ] Create a test build in the most recent Ubuntu LTS platform (Ubuntu 24.04
  as of writing this) and make sure it works:
  - [ ] Create a new development environment with Poetry.
  - [ ] Build the container image and ensure the development environment uses
    the new image.
  - [ ] Download the necessary assets using `./dev_scripts/inventory.py sync`
  - [ ] Run the Dangerzone tests.
  - [ ] Create a .deb package and install it system-wide.
  - [ ] Test some QA scenarios (see [Scenarios](#Scenarios) below).
- [ ] Create a test build in the most recent Fedora platform (Fedora 41 as of
  writing this) and make sure it works:
  - [ ] Create a new development environment with Poetry.
  - [ ] Build the container image and ensure the development environment uses
    the new image.
  - [ ] Download the necessary assets using `./dev_scripts/inventory.py sync`
  - [ ] Run the Dangerzone tests.
  - [ ] Create an .rpm package and install it system-wide.
  - [ ] Test some QA scenarios (see [Scenarios](#Scenarios) below).
- [ ] Create a test build in the most recent Qubes Fedora template (Fedora 40 as
  of writing this) and make sure it works:
  - [ ] Create a new development environment with Poetry.
  - [ ] Run the Dangerzone tests.
  - [ ] Create a Qubes .rpm package and install it system-wide.
  - [ ] Ensure that the Dangerzone application appears in the "Applications"
    tab.
  - [ ] Test some QA scenarios (see [Scenarios](#Scenarios) below) and make sure
    they spawn disposable qubes.

### Scenarios

#### 1. Dangerzone correctly identifies that Docker/Podman is not installed

_(Only for MacOS / Windows)_

Temporarily hide the Docker/Podman binaries, e.g., rename the `docker` /
`podman` binaries to something else. Then run Dangerzone. Dangerzone should
prompt the user to install Docker/Podman.

#### 2. Dangerzone correctly identifies that Docker is not running

_(Only for MacOS / Windows)_

Stop the Docker Desktop application. Then run Dangerzone. Dangerzone should
prompt the user to start Docker Desktop.


#### 3. Updating Dangerzone handles external state correctly.

_(Applies to Windows/MacOS)_

Install the previous version of Dangerzone, downloaded from the website.

Open the Dangerzone application and enable some non-default settings.
**If there are new settings, make sure to change those as well**.

Close the Dangerzone application and get the container image for that
version. For example:

```
$ docker images dangerzone.rocks/dangerzone
REPOSITORY                   TAG         IMAGE ID      CREATED       SIZE
dangerzone.rocks/dangerzone  <tag>       <image ID>    <date>        <size>
```

Then run the version under QA and ensure that the settings remain changed.

Afterwards check that new docker image was installed by running the same command
and seeing the following differences:

```
$ docker images dangerzone.rocks/dangerzone
REPOSITORY                   TAG         IMAGE ID        CREATED       SIZE
dangerzone.rocks/dangerzone  <other tag> <different ID>  <newer date>  <different size>
```

#### 4. Dangerzone successfully installs the container image

_(Only for Linux)_

Remove the Dangerzone container image from Docker/Podman. Then run Dangerzone.
Dangerzone should install the container image successfully.

#### 5. Dangerzone retains the settings of previous runs

Run Dangerzone and make some changes in the settings (e.g., change the OCR
language, toggle whether to open the document after conversion, etc.). Restart
Dangerzone. Dangerzone should show the settings that the user chose.

#### 6. Dangerzone reports failed conversions

Run Dangerzone and convert the `tests/test_docs/sample_bad_pdf.pdf` document.
Dangerzone should fail gracefully, by reporting that the operation failed, and
showing the following error message:

> The document format is not supported

#### 7. Dangerzone succeeds in converting multiple documents

Run Dangerzone against a list of documents, and tick all options. Ensure that:
* Conversions take place sequentially.
* Attempting to close the window while converting asks the user if they want to
  abort the conversions.
* Conversions are completed successfully.
* Conversions show individual progress in real-time (double-check for Qubes).
* _(Only for Linux)_ The resulting files open with the PDF viewer of our choice.
* OCR seems to have detected characters in the PDF files.
* The resulting files have been saved with the proper suffix, in the proper
  location.
* The original files have been saved in the `unsafe/` directory.

#### 8. Dangerzone is able to handle drag-n-drop

Run Dangerzone against a set of documents that you drag-n-drop. Files should be
added and conversion should run without issue.

> [!TIP]
> On our end-user container environments for Linux, we can start a file manager
> with `thunar &`.

#### 9. Dangerzone CLI succeeds in converting multiple documents

_(Only for Windows and Linux)_

Run Dangerzone CLI against a list of documents. Ensure that conversions happen
sequentially, are completed successfully, and we see their progress.

#### 10. Dangerzone can open a document for conversion via right-click -> "Open With"

_(Only for Windows, MacOS and Qubes)_

Go to a directory with office documents, right-click on one, and click on "Open
With". We should be able to open the file with Dangerzone, and then convert it.

#### 11. Dangerzone shows helpful errors for setup issues on Qubes

_(Only for Qubes)_

Check what errors does Dangerzone throw in the following scenarios. The errors
should point the user to the Qubes notifications in the top-right corner:

1. The `dz-dvm` template does not exist. We can trigger this scenario by
   temporarily renaming this template.
2. The Dangerzone RPC policy does not exist. We can trigger this scenario by
   temporarily renaming the `dz.Convert` policy.
3. The `dz-dvm` disposable Qube cannot start due to insufficient resources. We
   can trigger this scenario by temporarily increasing the minimum required RAM
   of the `dz-dvm` template to more than the available amount.
