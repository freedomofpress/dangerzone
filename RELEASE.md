# Release instructions

This section documents how we currently release Dangerzone for the different distributions we support.

## Pre-release

Here is a list of tasks that should be done before issuing the release:

- [ ] Create a new issue named **QA and Release for version \<VERSION\>**, to track the general progress.
      You can generate its content with the the `poetry run ./dev_scripts/generate-release-tasks.py` command.
- [ ] [Add new Linux platforms and remove obsolete ones](https://github.com/freedomofpress/dangerzone/blob/main/RELEASE.md#add-new-linux-platforms-and-remove-obsolete-ones)
- [ ] Bump the Python dependencies using `poetry lock`
- [ ] Update `version` in `pyproject.toml`
- [ ] Update `share/version.txt`
- [ ] Update the "Version" field in `install/linux/dangerzone.spec`
- [ ] Bump the Debian version by adding a new changelog entry in `debian/changelog`
- [ ] [Bump the minimum Docker Desktop versions](https://github.com/freedomofpress/dangerzone/blob/main/RELEASE.md#bump-the-minimum-docker-desktop-version) in `isolation_provider/container.py`
- [ ] Update screenshot in `README.md`, if necessary
- [ ] CHANGELOG.md should be updated to include a list of all major changes since the last release
- [ ] A draft release should be created. Copy the release notes text from the template at [`docs/templates/release-notes`](https://github.com/freedomofpress/dangerzone/tree/main/docs/templates/)
- [ ] Do the QA tasks

## Add new Linux platforms and remove obsolete ones

Our currently supported Linux OSes are Debian, Ubuntu, Fedora (we treat Qubes OS
as a special case of Fedora, release-wise). For each of these platforms, we need
to check if a new version has been added, or if an existing one is now EOL
(https://endoflife.date/ is handy for this purpose).

In case of a new version (beta, RC, or official release):

1. Add it in our CI workflows, to test if that version works.
   * See `.circleci/config.yml` and `.github/workflows/ci.yml`, as well as
     `dev_scripts/env.py` and `dev_scripts/qa.py`.
2. Do a test of this version locally with `dev_scripts/qa.py`. Focus on the
   GUI part, since the basic functionality is already tested by our CI
   workflows.
3. Add the new version in our `INSTALL.md` document, and drop a line in our
   `CHANGELOG.md`.
4. If that version is a new stable release, update the `RELEASE.md` and
   `BUILD.md` files where necessary.
4. Send a PR with the above changes.

In case of the removal of a version:

1. Remove any mention to this version from our repo.
   * Consult the previous paragraph, but also `grep` your way around.
2. Add a notice in our `CHANGELOG.md` about the version removal.

## Bump the minimum Docker Desktop version

We embed the minimum docker desktop versions inside Dangerzone, as an incentive for our macOS and Windows users to upgrade to the latests version.

You can find the latest version at the time of the release by looking at [their release notes](https://docs.docker.com/desktop/release-notes/)

## Large Document Testing

Parallel to the QA process, the release candidate should be put through the large document tests in a dedicated machine to run overnight.

Follow the instructions in `docs/developer/TESTING.md` to run the tests.

These tests will identify any regressions or progression in terms of document coverage.

## Release

Once we are confident that the release will be out shortly, and doesn't need any more changes:

- [ ] Create a PGP-signed git tag for the version, e.g., for dangerzone `v0.1.0`:

  ```bash
  git tag -s v0.1.0
  git push origin v0.1.0
  ```
  **Note**: release candidates are suffixed by `-rcX`.

> [!IMPORTANT]
> Because we don't have [reproducible builds](https://github.com/freedomofpress/dangerzone/issues/188)
> yet, building the Dangerzone container image in various platforms would lead
> to different container image IDs / hashes, due to different timestamps. To
> avoid this issue, we should build the final container image for x86_64
> architectures on **one** platform, and then copy it to the rest of the
> platforms, before creating our .deb / .rpm / .msi / app bundles.

### macOS Release

> [!TIP]
> You can automate these steps from your macOS terminal app with:
>
> ```
> export APPLE_ID=<email>
> make build-macos-intel  # for Intel macOS
> make build-macos-arm    # for Apple Silicon macOS
> ```

The following needs to happen for both Silicon and Intel chipsets.

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

Here is what you need to do:

- [ ] Verify and install the latest supported Python version from
  [python.org](https://www.python.org/downloads/macos/) (do not use the one from
  brew as it is known to [cause issues](https://github.com/freedomofpress/dangerzone/issues/471))

- [ ] Checkout the dependencies, and clean your local copy:

  ```bash

  # In case of a new Python installation or minor version upgrade, e.g., from
  # 3.11 to 3.12, reinstall Poetry
  python3 -m pip install poetry poetry-plugin-export

  # You can verify the correct Python version is used
  poetry debug info

  # Replace with the actual version
  export DZ_VERSION=$(cat share/version.txt)

  # Verify and checkout the git tag for this release:
  git checkout -f v$VERSION

  # Clean the git repository
  git clean -df

  # Clean up the environment
  poetry env remove --all

  # Install the dependencies
  poetry install --sync
  ```

- [ ] Build the container image and the OCR language data

  ```bash
  poetry run ./install/common/build-image.py
  poetry run ./install/common/download-tessdata.py

  # Copy the container image to the assets folder
  cp share/container.tar.gz ~dz/release-assets/$VERSION/dangerzone-$VERSION-arm64.tar.gz
  cp share/image-id.txt ~dz/release-assets/$VERSION/.
  ```

- [ ] Build the app bundle

  ```bash
  poetry run ./install/macos/build-app.py
  ```

- [ ] Sign the application bundle, and notarize it

  You need to run this command as the account that has access to the code signing certificate

  This command assumes that you have created, and stored in the Keychain, an
  application password associated with your Apple Developer ID, which will be
  used specifically for `notarytool`.

  ```bash
  # Sign the .App and make it a .dmg
  poetry run ./install/macos/build-app.py --only-codesign

  # Notarize it. You must run this command from the MacOS UI
  # from a terminal application.
  xcrun notarytool submit ./dist/Dangerzone.dmg --apple-id $APPLE_ID --keychain-profile "dz-notarytool-release-key" --wait && xcrun stapler staple dist/Dangerzone.dmg

  # Copy the .dmg to the assets folder
  ARCH=$(uname -m)
  if [ "$ARCH" = "x86_64" ]; then
      ARCH="i686"
  fi
  cp dist/Dangerzone.dmg ~dz/release-assets/$VERSION/Dangerzone-$VERSION-$ARCH.dmg
  ```

### Windows Release

The Windows release is performed in a Windows 11 virtual machine (as opposed to a physical one).

#### Initial Setup

- Download a VirtualBox VM image for Windows from here: https://developer.microsoft.com/en-us/windows/downloads/virtual-machines/ and import it into VirtualBox. Also install the Oracle VM VirtualBox Extension Pack.
- Install updates
- Install git for Windows from https://git-scm.com/download/win, and clone the dangerzone repo
- Follow the Windows build instructions in `BUILD.md`, except:
  - Don't install Docker Desktop (it won't work without nested virtualization)
  - Install the Windows SDK from here: https://developer.microsoft.com/en-us/windows/downloads/windows-sdk/ and add `C:\Program Files (x86)\Microsoft SDKs\ClickOnce\SignTool` to the path (you'll need it for `signtool.exe`)
  - You'll also need the Windows codesigning certificate installed on the VM

#### Releasing and Signing

- [ ] Checkout the dependencies, and clean your local copy:
  ```bash
  # In case of a new Python installation or minor version upgrade, e.g., from
  # 3.11 to 3.12, reinstall Poetry
  python3 -m pip install poetry poetry-plugin-export

  # You can verify the correct Python version is used
  poetry debug info

  # Replace with the actual version
  export DZ_VERSION=$(cat share/version.txt)

  # Verify and checkout the git tag for this release:
  git checkout -f v$VERSION

  # Clean the git repository
  git clean -df

  # Clean up the environment
  poetry env remove --all

  # Install the dependencies
  poetry install --sync
  ```

- [ ] Copy the container image into the VM
  > [!IMPORTANT]
  > Instead of running `python .\install\windows\build-image.py` in the VM, run the build image script on the host (making sure to build for `linux/amd64`). Copy `share/container.tar.gz` and `share/image-id.txt` from the host into the `share` folder in the VM.
- [ ] Run `poetry run .\install\windows\build-app.bat`
- [ ] When you're done you will have `dist\Dangerzone.msi`

Rename `Dangerzone.msi` to `Dangerzone-$VERSION.msi`.

### Linux release

> [!TIP]
> You can automate these steps from any Linux distribution with:
>
> ```
> make build-linux
> ```
>
> You can then add the created artifacts to the appropriate APT/YUM repo.

Below we explain how we build packages for each Linux distribution we support.

#### Debian/Ubuntu

Because the Debian packages do not contain compiled Python code for a specific
Python version, we can create a single Debian package and use it for all of our
Debian-based distros.

Create a Debian Bookworm development environment. You can [follow the
instructions in our build section](https://github.com/freedomofpress/dangerzone/blob/main/BUILD.md#debianubuntu),
or create your own locally with:

```sh
# Create and run debian bookworm development environment
./dev_scripts/env.py --distro debian --version bookworm build-dev
./dev_scripts/env.py --distro debian --version bookworm run --dev bash

# Build the latest container
./dev_scripts/env.py --distro debian --version bookworm run --dev bash -c "cd dangerzone && poetry run ./install/common/build-image.py"

# Create a .deb
./dev_scripts/env.py --distro debian --version bookworm run --dev bash -c "cd dangerzone && ./install/linux/build-deb.py"
```

Publish the .deb under `./deb_dist` to the
[`freedomofpress/apt-tools-prod`](https://github.com/freedomofpress/apt-tools-prod)
repo, by sending a PR. Follow the instructions in that repo on how to do so.

#### Fedora

> **NOTE**: This procedure will have to be done for every supported Fedora version.
>
> In this section, we'll use Fedora 41 as an example.

Create a Fedora development environment. You can [follow the
instructions in our build section](https://github.com/freedomofpress/dangerzone/blob/main/BUILD.md#fedora),
or create your own locally with:

```sh
./dev_scripts/env.py --distro fedora --version 41 build-dev

# Build the latest container (skip if already built):
./dev_scripts/env.py --distro fedora --version 41 run --dev bash -c "cd dangerzone && poetry run ./install/common/build-image.py"

# Create a .rpm:
./dev_scripts/env.py --distro fedora --version 41 run --dev bash -c "cd dangerzone && ./install/linux/build-rpm.py"
```

Publish the .rpm under `./dist` to the
[`freedomofpress/yum-tools-prod`](https://github.com/freedomofpress/yum-tools-prod) repo, by sending a PR. Follow the instructions in that repo on how to do so.

#### Qubes

Create a .rpm for Qubes:

```sh
./dev_scripts/env.py --distro fedora --version 41 run --dev bash -c "cd dangerzone && ./install/linux/build-rpm.py --qubes"
```

and similarly publish it to the [`freedomofpress/yum-tools-prod`](https://github.com/freedomofpress/yum-tools-prod)
repo.

## Publishing the Release

To publish the release, you can follow these steps:

- [ ] Create an archive of the Dangerzone source in `tar.gz` format:
  ```bash
  export VERSION=$(cat share/version.txt)
  git archive --format=tar.gz -o dangerzone-${VERSION:?}.tar.gz --prefix=dangerzone/ v${VERSION:?}
  ```

- [ ] Run container scan on the produced container images (some time may have passed since the artifacts were built)
  ```bash
  gunzip --keep -c ./share/container.tar.gz > /tmp/container.tar
  docker pull anchore/grype:latest
  docker run --rm -v /tmp/container.tar:/container.tar anchore/grype:latest /container.tar
  ```

- [ ] Collect the assets in a single directory, calculate their SHA-256 hashes, and sign them.
  There is an `./dev_scripts/sign-assets.py` script to automate this task.

  **Important:** Before running the script, make sure that it's the same container images as
  the ones that are shipped in other platforms (see our [Pre-release](#Pre-release) section)

  ```bash
  # Sign all the assets
  ./dev_scripts/sign-assets.py ~/release-assets/$VERSION/github --version $VERSION
  ```

- [ ] Upload all the assets to the draft release on GitHub.
  ```bash
  find ~/release-assets/$VERSION/github | xargs -n1 ./dev_scripts/upload-asset.py --token ~/token --draft
  ```

- [ ] Update the [Dangerzone website](https://github.com/freedomofpress/dangerzone.rocks) to link to the new installers.
- [ ] Update the brew cask release of Dangerzone with a [PR like this one](https://github.com/Homebrew/homebrew-cask/pull/116319)
- [ ] Update version and download links in `README.md`

## Post-release

- [ ] Toot release announcement on our mastodon account @dangerzone@fosstodon.org
- [ ] Extend the `check_repos.yml` CI test for the newly added platforms
