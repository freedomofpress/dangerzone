# Release instructions

This section documents the release process. Unless you're a dangerzone developer making a release, you'll probably never need to follow it.

## Pre-release

Before making a release, all of these should be complete:

- [ ] [Add new Linux platforms and remove obsolete ones](#add-new-platforms-and-remove-obsolete-ones)
- [ ] Bump the Python dependencies using `poetry lock`
- [ ] [Check for new PySide6 versions](#check-for-new-pyside6-versions)
- [ ] Update `version` in `pyproject.toml`
- [ ] Update `share/version.txt`
- [ ] Update the "Version" field in `install/linux/dangerzone.spec`
- [ ] Update version and download links in `README.md`, and screenshot if necessary
- [ ] CHANGELOG.md should be updated to include a list of all major changes since the last release
- [ ] Copy the entirety of these instructions onto a new issue and call it **QA and Release version \<VERSION\>**
- [ ] Create a PGP-signed git tag for the version, e.g. for dangerzone `v0.1.0`, the is created with:

  ```
  git tag -s v0.1.0
  git push origin v0.1.0
  ```
  **Note**: release candidates are suffixed by `-rcX`.

## Add new platforms and remove obsolete ones

Our currently supported Linux OSes are Debian, Ubuntu, Fedora (we treat Qubes OS
as a special case of Fedora, release-wise). For each of these platforms, we need
to check if a new version has been added, or if an existing one is now EOL
(https://endoflife.date/ is handy for this purpose).

In case of a new version:

1. Add it in our CI workflows, to test if that version works.
   * See `.circleci/config.yml` and `.github/workflows/ci.yml`, as well as
     `dev_scripts/env.py` and `dev_scripts/qa.py`.
2. Do a test of this version locally with `dev_scripta/qa.py`. Focus on the
   GUI part, since the basic functionality is already tested by our CI
   workflows.
3. Add the new version in our `INSTALL.md` document, and drop a line in our
   `CHANGELOG.md`.
4. If that version is a new stable release, update the `RELEASE.md` and
   `BUILD.md` files where necesary.
4. Send a PR with the above changes.

In case of an EOL version:

1. Remove any mention to this version from our repo.
   * Consult the previous paragraph, but also `grep` your way around.
2. Add a notice in our `CHANGELOG.md` about the version removal.

## Check for new PySide6 versions

When a new PySide6 version has been released, we will get notified  because the
nightly CI tests on `freedomofpres/python3-pyside6-rpm` will start failing.

Even if we miss these notifications, we will see failing builds in the
Dangerzone repo once we update our `poetry.lock` file. More specifically,
`./dev_scripts/env.py --distro fedora [...]  build` will start failing, because
it won't be able to find a PySide6 RPM for the new version.

The Dangerzone maintainer should do the following:

1. Check the changelog for the new PySide6 version, and ensure it doesn't
   introduce a breaking change.
2. Clone locally the https://github.com/freedomofpress/python3-pyside6-rpm repo.
3. Bump the PySide6 version and create a new PySide6 RPM for the supported
   Fedora versions.
4. Copy it under the `dist/` directory of the Dangerzone repo.
5. Create an end-user build environment with `./dev_scripts/env.py --distro fedora [...]  build`
6. Test that the Dangerzone UI works properly.
7. Ship the new PySide6 RPMs in our Fedora repo
   (https://github.com/freedomofpress/yum-tools-prod)
8. Send a PR to the Dangerzone repo, with the new `poetry.lock` file.

## Large Document Testing

Parallel to the QA process, the release candidate should be put through the large document tests in a dedicated machine to run overnight.

Follow the instructions in `docs/developer/TESTING.md` to run the tests.

These tests will identify any regressions or progression in terms of document coverage.

## QA

To ensure that new releases do not introduce regressions, and support existing
and newer platforms, we have to do the following:

- [ ] Make sure that the tip of the `main` branch passes the CI tests.
- [ ] Make sure that the Apple account has a valid application password and has
      agreed to the latest Apple terms (see [macOS release](#macos-release)
      section).
- [ ] Create a test build in Windows and make sure it works:
  - [ ] Check if the suggested Python version is still supported.
  - [ ] Create a new development environment with Poetry.
  - [ ] Build the container image and ensure the development environment uses
    the new image.
  - [ ] Run the Dangerzone tests.
  - [ ] Build and run the Dangerzone .exe
  - [ ] Test some QA scenarios (see [Scenarios](#Scenarios) below).
- [ ] Create a test build in macOS (Intel CPU) and make sure it works:
  - [ ] Check if the suggested Python version is still supported.
  - [ ] Create a new development environment with Poetry.
  - [ ] Build the container image and ensure the development environment uses
    the new image.
  - [ ] Run the Dangerzone tests.
  - [ ] Create and run an app bundle.
  - [ ] Test some QA scenarios (see [Scenarios](#Scenarios) below).
- [ ] Create a test build in macOS (M1/2 CPU) and make sure it works:
  - [ ] Check if the suggested Python version is still supported.
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
- [ ] Create a test build in the most recent Fedora platform (Fedora 39 as of
  writing this) and make sure it works:
  - [ ] Create a new development environment with Poetry.
  - [ ] Build the container image and ensure the development environment uses
    the new image.
  - [ ] Run the Dangerzone tests.
  - [ ] Create an .rpm package and install it system-wide.
  - [ ] Test some QA scenarios (see [Scenarios](#Scenarios) below).
- [ ] Create a test build in the most recent Qubes Fedora template (Fedora 39 as
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
$ docker images dangerzone.rocks/dangerzone:latest
REPOSITORY                   TAG         IMAGE ID      CREATED       SIZE
dangerzone.rocks/dangerzone  latest      <image ID>    <date>        <size>
```

Then run the version under QA and ensure that the settings remain changed.

Afterwards check that new docker image was installed by running the same command
and seeing the following differences:

```
$ docker images dangerzone.rocks/dangerzone:latest
REPOSITORY                   TAG         IMAGE ID        CREATED       SIZE
dangerzone.rocks/dangerzone  latest      <different ID>  <newer date>  <different size>
```

#### 4. Dangerzone successfully installs the container image

_(Linux)_

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

#### 8. Dangerzone CLI succeeds in converting multiple documents

_(Only for Windows and Linux)_

Run Dangerzone CLI against a list of documents. Ensure that conversions happen
sequentially, are completed successfully, and we see their progress.

#### 9. Dangerzone can open a document for conversion via right-click -> "Open With"

_(Only for Windows, MacOS and Qubes)_

Go to a directory with office documents, right-click on one, and click on "Open
With". We should be able to open the file with Dangerzone, and then convert it.

#### 10. Dangerzone shows helpful errors for setup issues on Qubes

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

## Release

> [!IMPORTANT]
> Because we don't have [reproducible builds](https://github.com/freedomofpress/dangerzone/issues/188)
> yet, building the Dangerzone container image in various platforms would lead
> to different container image IDs / hashes, due to different timestamps. To
> avoid this issue, we should build the final container image for x86_64
> architectures on **one** platform, and then copy it to the rest of the
> platforms, before creating our .deb / .rpm / .msi / app bundles.

### macOS Release

#### Initial Setup
- Build machine must have:
  - Apple-trusted `Developer ID Application: Freedom of the Press Foundation (94ZZGGGJ3W)` code-signing certificates installed
- Apple account must have:
  - A valid application password for `notarytool` in the Keychain. You can verify
    this by running: `xcrun notarytool history --apple-id "<email>" --keychain-profile "dz-notarytool-release-key"`. If you don't find it, you can add it to the Keychain by running
    `xcrun notarytool store-credentials dz-notarytool-release-key --apple-id <email> --team-id <team ID>`
    with the respective `email` and `team ID` (the latter can be obtained [here](https://developer.apple.com/help/account/manage-your-team/locate-your-team-id))
  - Agreed to any new terms and conditions. You can find those if you visit
    https://developer.apple.com and login with the proper Apple ID.

#### Releasing and Signing
- [ ] Verify and checkout the git tag for this release
- [ ] Run `poetry install`
- [ ] Run `poetry run ./install/macos/build-app.py`; this will make `dist/Dangerzone.app`
- [ ] Run `poetry run ./install/macos/build-app.py --only-codesign`; this will make `dist/Dangerzone.dmg`
  * You need to run this command as the account that has access to the code signing certificate
  * You must run this command from the MacOS UI, from a terminal application.
- [ ] Notarize it: `xcrun notarytool submit --apple-id "<email>" --keychain-profile "dz-notarytool-release-key" dist/Dangerzone.dmg`
  * In the end you'll get a `REQUEST_UUID`, which identifies the submission. Keep it to check on its status.
  * You need to change the `<email>` in the above command with the email
    associated with the Apple Developer ID.
  * This command assumes that you have created, and stored in the Keychain, an
    application password associated with your Apple Developer ID, which will be
    used specifically for `notarytool`.
- [ ] Wait for it to get approved, check status with: `xcrun notarytool info <REQUEST_UUID> --apple-id "<email>" --keychain-profile "dz-notarytool-release-key"`
  * If it gets rejected, you should be able to see why with the same command
    (or use the `log` option for a more verbose JSON output)
  * You will also receive an update in your email.
- [ ] After it's approved, staple the ticket: `xcrun stapler staple dist/Dangerzone.dmg`

This process ends up with the final file:

```
dist/Dangerzone.dmg
```

Rename `Dangerzone.dmg` to `Dangerzone-$VERSION.dmg`.

### Windows Release
The Windows release is performed in a Windows 11 virtual machine as opposed to a physical one.

#### Initial Setup

- Download a VirtualBox VM image for Windows from here: https://developer.microsoft.com/en-us/windows/downloads/virtual-machines/ and import it into VirtualBox. Also install the Oracle VM VirtualBox Extension Pack.
- Install updates
- Install git for Windows from https://git-scm.com/download/win, and clone the dangerzone repo
- Follow the Windows build instructions in `BUILD.md`, except:
  - Don't install Docker Desktop (it won't work without nested virtualization)
  - Install the Windows SDK from here: https://developer.microsoft.com/en-us/windows/downloads/windows-sdk/ and add `C:\Program Files (x86)\Microsoft SDKs\ClickOnce\SignTool` to the path (you'll need it for `signtool.exe`)
  - You'll also need the Windows codesigning certificate installed on the VM

#### Releasing and Signing

- [ ] Verify and checkout the git tag for this release
- [ ] Run `poetry install`
- [ ] Copy the container image into the VM
  > [!IMPORTANT]
  > Instead of running `python .\install\windows\build-image.py` in the VM, run the build image script on the host (making sure to build for `linux/amd64`). Copy `share/container.tar.gz` and `share/image-id.txt` from the host into the `share` folder in the VM
- [ ] Run `poetry run .\install\windows\build-app.bat`
- [ ] When you're done you will have `dist\Dangerzone.msi`

Rename `Dangerzone.msi` to `Dangerzone-$VERSION.msi`.

### Linux release

#### Debian/Ubuntu

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
python3 ./install/common/build-image.py
```

Create a .deb:

```sh
./install/linux/build-deb.py
```

Publish the .deb under `./deb_dist` to the
[`freedomofpress/apt-tools-prod`](https://github.com/freedomofpress/apt-tools-prod)
repo, by sending a PR. Follow the instructions in that repo on how to do so.

#### Fedora

> **NOTE**: This procedure will have to be done for every supported Fedora version.
>
> In this section, we'll use Fedora 39 as an example.

Create a Fedora development environment. You can [follow the
instructions in our build section](https://github.com/freedomofpress/dangerzone/blob/main/BUILD.md#fedora),
or create your own locally with:

```sh
./dev_scripts/env.py --distro fedora --version 39 build-dev
./dev_scripts/env.py --distro fedora --version 39 run --dev bash
cd dangerzone
```

Build the latest container:

```sh
python3 ./install/common/build-image.py
```

Create a .rpm:

```sh
./install/linux/build-rpm.py
```

Publish the .rpm under `./dist` to the
[`freedomofpress/yum-tools-prod`](https://github.com/freedomofpress/yum-tools-prod) repo, by sending a PR. Follow the instructions in that repo on how to do so.

#### Qubes

Create a .rpm for Qubes:

```sh
./install/linux/build-rpm.py --qubes
```

and similarly publish it to the [`freedomofpress/yum-tools-prod`](https://github.com/freedomofpress/yum-tools-prod)
repo.

## Publishing the Release

To publish the release:

- [ ] Run container scan on the produced container images (some time may have passed since the artifacts were built)
- [ ] Create a new release on GitHub and upload the macOS and Windows installers.
  * Copy the release notes text from the template at [`docs/templates/release-notes`](https://github.com/freedomofpress/dangerzone/tree/main/docs/templates/)
  * You can use `./dev_scripts/upload-asset.py`, if you want to upload an asset
    using an access token.
- [ ] Upload the `container.tar.gz` i686 image that was created in the previous step

  **Important:** Make sure that it's the same container image as the ones that
  are shipped in other platforms (see our [Pre-release](#Pre-release) section)

- [ ] Update the [Installing Dangerzone](INSTALL.md) page
- [ ] Update the [Dangerzone website](https://github.com/freedomofpress/dangerzone.rocks) to link to the new installers
- [ ] Update the brew cask release of Dangerzone with a [PR like this one](https://github.com/Homebrew/homebrew-cask/pull/116319)
- [ ] Toot release announcement on our mastodon account @dangerzone@fosstodon.org
