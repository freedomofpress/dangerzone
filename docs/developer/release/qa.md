# QA

To ensure that new releases do not introduce regressions, and support existing
and newer platforms, the produced packages are tested.

Here is a list of checks. Some of them manual, and the release
manager needs to follow them across several OSes.

Because some of the checks are repetitive, a script automates some of the QA
(see [Scripted QA](#scripted-qa)). It runs the tasks, prompting you when it needs manual intervention.

It can be run with:

```bash
poetry run ./dev_scripts/qa.py {distro}-{version}
```

A large collection of documents is also available, that can be tested against the `main` branch
prior to a release (see [Large Document Testing](#large-document-testing)).

## The checklist

- [ ] Make sure that the tip of the `main` branch passes the CI tests.
- [ ] Create a test build in Windows and make sure it works:
  - [ ] Check if the suggested Python version is still supported.
  - [ ] Create a new development environment with Poetry.
  - [ ] Build the container image and ensure the development environment uses
    the new image.
  - [ ] Download the necessary assets using `poetry run mazette install`
  - [ ] Run the Dangerzone tests.
  - [ ] Build and run the Dangerzone .exe
  - [ ] Test some QA scenarios (see [Scenarios](#Scenarios) below).
- [ ] Create a test build in macOS (Intel CPU) and make sure it works:
  - [ ] Check if the suggested Python version is still supported.
  - [ ] Create a new development environment with Poetry.
  - [ ] Build the container image and ensure the development environment uses
    the new image.
  - [ ] Download the necessary assets using `poetry run mazette install`
  - [ ] Run the Dangerzone tests.
  - [ ] Create and run an app bundle.
  - [ ] Test some QA scenarios (see [Scenarios](#Scenarios) below).
- [ ] Create a test build in macOS (M1/2 CPU) and make sure it works:
  - [ ] Check if the suggested Python version is still supported.
  - [ ] Create a new development environment with Poetry.
  - [ ] Build the container image and ensure the development environment uses
    the new image.
  - [ ] Download the necessary assets using `poetry run mazette install`
  - [ ] Run the Dangerzone tests.
  - [ ] Create and run an app bundle.
  - [ ] Test some QA scenarios (see [Scenarios](#Scenarios) below).
- [ ] Create a test build in the most recent Ubuntu LTS platform (Ubuntu 24.04
  as of writing this) and make sure it works:
  - [ ] Create a new development environment with Poetry.
  - [ ] Build the container image and ensure the development environment uses
    the new image.
  - [ ] Download the necessary assets using `poetry run mazette install`
  - [ ] Run the Dangerzone tests.
  - [ ] Create a .deb package and install it system-wide.
  - [ ] Test some QA scenarios (see [Scenarios](#Scenarios) below).
- [ ] Create a test build in the most recent Fedora platform (Fedora 41 as of
  writing this) and make sure it works:
  - [ ] Create a new development environment with Poetry.
  - [ ] Build the container image and ensure the development environment uses
    the new image.
  - [ ] Download the necessary assets using `poetry run mazette install`
  - [ ] Run the Dangerzone tests.
  - [ ] Create an .rpm package and install it system-wide.
  - [ ] Test some QA scenarios (see [Scenarios](#Scenarios) below).
- [ ] Create a test build in the most recent Qubes Fedora template (Fedora 41 as
  of writing this) and make sure it works:
  - [ ] Create a new development environment with Poetry.
  - [ ] Run the Dangerzone tests.
  - [ ] Create a Qubes .rpm package and install it system-wide.
  - [ ] Ensure that the Dangerzone application appears in the "Applications"
    tab.
  - [ ] Test some QA scenarios (see [Scenarios](#Scenarios) below) and make sure
    they spawn disposable qubes.

## Scenarios

### 1. Updating Dangerzone handles external state correctly.

_(Applies to Windows/MacOS)_

Install the previous version of Dangerzone, downloaded from the website.

Open the Dangerzone application and enable some non-default settings.
**If there are new settings, make sure to change those as well**.

Close the Dangerzone application and get the container image for that
version. For example:

```bash
$ dangerzone-machine raw images ghcr.io/freedomofpress/dangerzone/v1
REPOSITORY                            TAG         IMAGE ID      CREATED       SIZE
ghcr.io/freedomofpress/dangerzone/v1  <tag>       <image ID>    <date>        <size>
```

Then run the version under QA and ensure that the settings remain changed.

Afterwards check that new docker image was installed by running the same command
and seeing the following differences:

```bash
$ dangerzone-machine raw images ghcr.io/freedomofpress/dangerzone/v1
REPOSITORY                            TAG         IMAGE ID        CREATED       SIZE
ghcr.io/freedomofpress/dangerzone/v1  <other tag> <different ID>  <newer date>  <different size>
```

### 2. Dangerzone successfully installs the container image

_(Only for Linux)_

Remove the Dangerzone container image and podman machine with:

```bash
dangerzone-machine reset
```

Then run Dangerzone. Dangerzone should install the podman machine and container image successfully.

### 3. Dangerzone retains the settings of previous runs

Run Dangerzone and make some changes in the settings (e.g., change the OCR
language, toggle whether to open the document after conversion, etc.). Restart
Dangerzone. Dangerzone should show the settings that the user chose.

### 4. Dangerzone reports failed conversions

Run Dangerzone and convert the `tests/test_docs/sample_bad_pdf.pdf` document.
Dangerzone should fail gracefully, by reporting that the operation failed, and
showing the following error message:

> The document format is not supported

### 5. Dangerzone succeeds in converting multiple documents

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

### 6. Dangerzone is able to handle drag-n-drop

Run Dangerzone against a set of documents that you drag-n-drop. Files should be
added and conversion should run without issue.

> [!TIP]
> On our end-user container environments for Linux, we can start a file manager
> with `thunar &`.

### 7. Dangerzone CLI succeeds in converting multiple documents

_(Only for Windows and Linux)_

Run Dangerzone CLI against a list of documents. Ensure that conversions happen
sequentially, are completed successfully, and we see their progress.

### 8. Dangerzone can open a document for conversion via right-click -> "Open With"

_(Only for Windows, MacOS and Qubes)_

Go to a directory with office documents, right-click on one, and click on "Open
With". We should be able to open the file with Dangerzone, and then convert it.

### 9. Dangerzone shows helpful errors for setup issues on Qubes

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

## Large Document Testing

Parallel to the QA process, the release candidate should be put through the large document tests. This can be done by rebasing [the currently open Pull Request](https://github.com/freedomofpress/dangerzone/pull/1098).

These tests will identify any regressions or progression in terms of document coverage.

## Scripted QA

The `dev_scripts/qa.py` script runs the above QA steps for a supported platform,
in order to make sure that the dev does not skip something.

The idea behind this script is that it will present each step to the user and
ask them to perform it manually and specify it passes, in order to continue to
the next one. For specific steps, it allows the user to run them automatically.
In steps that require a Dangerzone dev environment, this script uses the
`env.py` script to create one.

Including all the supported platforms in this script is still a work in
progress.
