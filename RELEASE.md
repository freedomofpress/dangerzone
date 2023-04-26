# Release instructions

This section documents the release process. Unless you're a dangerzone developer making a release, you'll probably never need to follow it.

## QA

To ensure that new releases do not introduce regressions, and support existing
and newer platforms, we have to do the following:

- [ ] In `.circleci/config.yml`, add new platforms and remove obsolete platforms
- [ ] Make sure that the tip of the `main` branch passes the CI tests.
- [ ] Create a test build in Windows and make sure it works:
  - [ ] Create a new development environment with Poetry.
  - [ ] Build the container image and ensure the development environment uses
    the new image.
  - [ ] Run the Dangerzone tests.
  - [ ] Build and run the Dangerzone .exe
  - [ ] Test some QA scenarios (see [Scenarios](#Scenarios) below).
- [ ] Create a test build in macOS (Intel CPU) and make sure it works:
  - [ ] Create a new development environment with Poetry.
  - [ ] Build the container image and ensure the development environment uses
    the new image.
  - [ ] Run the Dangerzone tests.
  - [ ] Create and run an app bundle.
  - [ ] Test some QA scenarios (see [Scenarios](#Scenarios) below).
- [ ] Create a test build in macOS (M1/2 CPU) and make sure it works:
  - [ ] Create a new development environment with Poetry.
  - [ ] Build the container image and ensure the development environment uses
    the new image.
  - [ ] Run the Dangerzone tests.
  - [ ] Create and run an app bundle.
  - [ ] Test some QA scenarios (see [Scenarios](#Scenarios) below).
- [ ] Create a test build in the most recent Ubuntu LTS platform (Ubuntu 22.04
  as of writing this) and make sure it works:
  - [ ] Create a new development environment with Poetry.
  - [ ] Build the container image and ensure the development environment uses
    the new image.
  - [ ] Run the Dangerzone tests.
  - [ ] Create a .deb package and install it system-wide.
  - [ ] Test some QA scenarios (see [Scenarios](#Scenarios) below).
- [ ] Create a test build in the most recent Fedora platform (Fedora 38 as of
  writing this) and make sure it works:
  - [ ] Create a new development environment with Poetry.
  - [ ] Build the container image and ensure the development environment uses
    the new image.
  - [ ] Run the Dangerzone tests.
  - [ ] Create an .rpm package and install it system-wide.
  - [ ] Test some QA scenarios (see [Scenarios](#Scenarios) below).

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

#### 3. Dangerzone successfully installs the container image

Remove the Dangerzone container image from Docker/Podman. Then run Dangerzone.
Danerzone should install the container image successfully.

#### 4. Dangerzone retains the settings of previous runs

Run Dangerzone and make some changes in the settings (e.g., change the OCR
language, toggle whether to open the document after conversion, etc.). Restart
Dangerzone. Dangerzone should show the settings that the user chose.

#### 5. Dangerzone reports failed conversions

Run Dangerzone and convert the `tests/test_docs/sample_bad_pdf.pdf` document.
Dangerzone should fail gracefully, by reporting that the operation failed, and
showing the last error message.

#### 6. Dangerzone succeeds in converting multiple documents

Run Dangerzone against a list of documents, and tick all options. Ensure that:
* Conversions take place sequentially.
* Attempting to close the window while converting asks the user if they want to
  abort the conversions.
* Conversions are completed successfully.
* Conversions show individual progress.
* _(Only for Linux)_ The resulting files open with the PDF viewer of our choice.
* OCR seems to have detected characters in the PDF files.
* The resulting files have been saved with the proper suffix, in the proper
  location.
* The original files have been saved in the `unsafe/` directory.

#### 7. Dangerzone CLI succeeds in converting multiple documents

_(Only for Windows and Linux)_

Run Dangerzone CLI against a list of documents. Ensure that conversions happen
sequentially, are completed successfully, and we see their progress.

#### 8. Dangerzone can open a document for conversion via right-click -> "Open With"

_(Only for Windows and MacOS)_

Go to a directory with office documents, right-click on one, and click on "Open
With". We should be able to open the file with Dangerzone, and then convert it.

#### 9. Updating Dangerzone handles external state correctly.

_(Applies to Linux/Windows/MacOS. For MacOS/Windows, it requires an installer
for the new version)_

Install the previous version of Dangerzone system-wide. Open the Dangerzone
application and enable some non-default settings. Close the Dangerzone
application and get the container image for that version. For example

```
$ podman images dangerzone.rocks/dangerzone:latest
REPOSITORY                   TAG         IMAGE ID      CREATED       SIZE
dangerzone.rocks/dangerzone  latest      <image ID>    <date>        <size>
```

_(use `docker` on Windows/MacOS)_

Install the new version of Dangerzone system-wide. Open the Dangerzone
application and make sure that the previously enabled settings still show up.
Also, ensure that Dangerzone reports that the new image has been installed, and
verify that it's different from the old one by doing:

```
$ podman images dangerzone.rocks/dangerzone:latest
REPOSITORY                   TAG         IMAGE ID        CREATED       SIZE
dangerzone.rocks/dangerzone  latest      <different ID>  <newer date>  <different size>
```

## Changelog, version, and signed git tag

Before making a release, all of these should be complete:

- [ ] Update `version` in `pyproject.toml`
- [ ] Update `share/version.txt`
- [ ] Update version and download links in `README.md`, and screenshot if necessary
- [ ] CHANGELOG.md should be updated to include a list of all major changes since the last release
- [ ] There must be a PGP-signed git tag for the version, e.g. for dangerzone 0.1.0, the tag must be `v0.1.0`

Before making a release, verify the release git tag:

```
git fetch
git tag -v v$VERSION
```

If the tag verifies successfully and check it out:

```
git checkout v$VERSION
```

## macOS release

To make a macOS release, go to macOS build machine:

- Build machine must have:
  - Apple-trusted `Developer ID Application: Freedom of the Press Foundation (94ZZGGGJ3W)` code-signing certificates installed
- Verify and checkout the git tag for this release
- Run `poetry install`
- Run `poetry run ./install/macos/build-app.py`; this will make `dist/Dangerzone.app`
- Run `poetry run ./install/macos/build-app.py --only-codesign`; this will make `dist/Dangerzone.dmg`
  * You need to run this command as the account that has access to the code signing certificate
  * You must run this command from the MacOS UI, from a terminal application.
- Notarize it: `xcrun altool --notarize-app --primary-bundle-id "press.freedom.dangerzone" -u "<email>" --file dist/Dangerzone.dmg`
  * You need to change the `<email>` in the above command with the email
    associated with the Apple Developer ID.
  * This command will ask you for a password. Prefer creating an application
    password associated with your Apple Developer ID, which will be used
    specifically for `altool`.
- Wait for it to get approved, check status with: `xcrun altool --notarization-history 0 -u "<email>"`
  * You will also receive an update in your email.
- (If it gets rejected, you can see why with: `xcrun altool --notarization-info $REQUEST_UUID -u "<email>"`)
- After it's approved, staple the ticket: `xcrun stapler staple dist/Dangerzone.dmg`

This process ends up with the final file:

```
dist/Dangerzone.dmg
```

Rename `Dangerzone.dmg` to `Dangerzone-$VERSION.dmg`.

## Windows release

### Set up a Windows 11 VM for making releases

- Download a VirtualBox VM image for Windows from here: https://developer.microsoft.com/en-us/windows/downloads/virtual-machines/ and import it into VirtualBox. Also install the Oracle VM VirtualBox Extension Pack.
- Install updates
- Install git for Windows from https://git-scm.com/download/win, and clone the dangerzone repo
- Follow the Windows build instructions in `BUILD.md`, except:
  - Don't install Docker Desktop (it won't work without nested virtualization)
  - Install the Windows SDK from here: https://developer.microsoft.com/en-us/windows/downloads/windows-sdk/ and add `C:\Program Files (x86)\Microsoft SDKs\ClickOnce\SignTool` to the path (you'll need it for `signtool.exe`)
  - You'll also need the Windows codesigning certificate installed on the VM

### Build the container image

Instead of running `python .\install\windows\build-image.py` in the VM, run the build image script on the host (making sure to build for `linux/amd64`). Copy `share/container.tar.gz` and `share/image-id.txt` from the host into the `share` folder in the VM

### Build the Dangerzone binary and installer

- Verify and checkout the git tag for this release
- Run `poetry install`
- Run `poetry run .\install\windows\build-app.bat`
- When you're done you will have `dist\Dangerzone.msi`

Rename `Dangerzone.msi` to `Dangerzone-$VERSION.msi`.

## Linux release

### Debian/Ubuntu

Because the Debian packages do not contain compiled Python code for a specific
Python version, we can create a single Debian package and use it for all of our
Debian-based distros.

Create a Debian Bookworm development environment. You can [follow the
instructions in our build section](https://github.com/freedomofpress/dangerzone/blob/main/BUILD.md#debianubuntu),
or create your own locally with:

```sh
./dev_scripts/env.py --distro debian --version bookworm build-dev
./dev_scripts/env.py --distro debian --version bookworm run --dev bash
cd dangerzone
```

Build the latest container:

```sh
./install/linux/build-image.sh
```

Create a .deb:

```sh
./install/linux/build-deb.py
```

Publish the .deb under `./deb_dist` to the
[`freedomofpress/apt-tools-prod`](https://github.com/freedomofpress/apt-tools-prod)
repo, by sending a PR. Follow the instructions in that repo on how to do so.

### Fedora

> **NOTE**: This procedure will have to be done for every supported Fedora version.
>
> In this section, we'll use Fedora 38 as an example.

Create a Fedora development environment. You can [follow the
instructions in our build section](https://github.com/freedomofpress/dangerzone/blob/main/BUILD.md#fedora),
or create your own locally with:

```sh
./dev_scripts/env.py --distro fedora --version 38 build-dev
./dev_scripts/env.py --distro fedora --version 38 run --dev bash
cd dangerzone
```

Build the latest container:

```sh
./install/linux/build-image.sh
```

Create a .rpm:

```sh
./install/linux/build-rpm.py
```

Publish the .rpm under `./dist` to the
[`freedomofpress/yum-tools-prod`](https://github.com/freedomofpress/yum-tools-prod) repo, by sending a PR. Follow the instructions in that repo on how to do so.


## Publishing the release

To publish the release:

- Create a new release on GitHub, put the changelog in the description of the release, and upload the macOS and Windows installers
- Update the [Installing Dangerzone](INSTALL.md) page
- Update the [Dangerzone website](https://github.com/freedomofpress/dangerzone.rocks) to link to the new installers
- Update the brew cask release of Dangerzone with a [PR like this one](https://github.com/Homebrew/homebrew-cask/pull/116319)
- Toot release announcement on our mastodon account @dangerzone@fosstodon.org
