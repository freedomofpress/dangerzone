# Build release artifacts

Follow the sections below, depending on the OS you want to build artifacts for.
Linux artifacts can be built on macOS, via the use of containers.

Automated instructions help build things quicker. For an explanation of what
they do under the hood, read [`docs/developer/doit.md`](../doit.md).

## macOS

### Automated

From your macOS terminal app:

- [ ] `export APPLE_ID=<email>` in your terminal session
- [ ] Build artifacts for Intel macOS with `make build-macos-intel`
- [ ] Build artifacts for Apple Silicon macOS with `make build-macos-arm`

### Manual steps

1. Checkout the dependencies, and clean your local copy:

   ```bash
   # Replace with the actual version
   export DZ_VERSION=$(cat share/version.txt)

   # Verify and checkout the git tag for this release:
   git checkout -f v$VERSION

   # Clean the git repository
   git clean -df

   # Clean up the environment
   poetry env remove --all

   # Install the dependencies
   poetry sync
   ```

2. Retrieve the container image and download the necessary assets:

   ```bash
   poetry run ./dev_scripts/dangerzone-image prepare-archive
    --image ghcr.io/freedomofpress/dangerzone/v1@sha256:${DIGEST}
    --output share/container.tar

   poetry run mazette install

   # Copy the container image to the assets folder
   cp share/container.tar ~dz/release-assets/$VERSION/dangerzone-$VERSION-arm64.tar
   ```

3. Build the app bundle

   ```bash
   poetry run ./install/macos/build-app.py
   ```

4. Sign the application bundle, and notarize it

   This command needs to run from an account with access to the code-signing certificate.

   This command assumes the Apple Developer ID application password is stored in the Keychain
   and used specifically for `notarytool`.

   ```bash
   # Sign the .App and make it a .dmg
   poetry run ./install/macos/build-app.py --only-codesign

   # Notarize it. This command must run from the MacOS UI,
   # inside a terminal application.
   xcrun notarytool submit ./dist/Dangerzone.dmg --apple-id $APPLE_ID --keychain-profile "dz-notarytool-release-key" --wait && xcrun stapler staple dist/Dangerzone.dmg

   # Copy the .dmg to the assets folder
   ARCH=$(uname -m)
   if [ "$ARCH" = "x86_64" ]; then
       ARCH="i686"
   fi
   cp dist/Dangerzone.dmg ~dz/release-assets/$VERSION/Dangerzone-$VERSION-$ARCH.dmg
   ```

## Windows

- [ ] Checkout the dependencies, and clean the local copy:

  ```bash
  # Replace with the actual version
  export DZ_VERSION=$(cat share/version.txt)

  # Verify and checkout the git tag for this release:
  git checkout -f v$VERSION

  # Clean the git repository
  git clean -df

  # Clean up the environment
  poetry env remove --all

  # Install the dependencies
  poetry sync
  ```
- [ ] Download the container image with signatures:
  ```bash
  poetry run ./dev_scripts/dangerzone-image prepare-archive
    --image ghcr.io/freedomofpress/dangerzone/v1@sha256:${DIGEST}
    --output share/container.tar
  ```
- [ ] Download the necessary assets with `poetry run mazette install`
- [ ] Run `poetry run .\install\windows\build-app.bat`
- After completion, the installer will be available at `dist\Dangerzone.msi`
- [ ] Rename `Dangerzone.msi` to `Dangerzone-$VERSION.msi`.

## Linux

### Automated

- [ ] Run `make build-linux` (not necessary if you've previously built artifacts for macOS)

### Manual steps

Below we explain how we build packages for each Linux distribution we support.

#### Debian/Ubuntu

Because the Debian packages do not contain compiled Python code for a specific
Python version, a single Debian package can be used for all of our
Debian-based distros.

Create a Debian Bookworm development environment. [Follow the
instructions in the build section](https://github.com/freedomofpress/dangerzone/blob/main/BUILD.md#debianubuntu),
or create it locally with:

```bash
# Create and run debian bookworm development environment
./dev_scripts/env.py --distro debian --version bookworm build-dev
./dev_scripts/env.py --distro debian --version bookworm run --dev bash

# Get the vendorized assets
poetry run mazette install

# Retrieve the latest container
poetry run ./dev_scripts/dangerzone-image prepare-archive
    --image ghcr.io/freedomofpress/dangerzone/v1@sha256:${DIGEST}
    --output share/container.tar

# Create a .deb
./dev_scripts/env.py --distro debian --version bookworm run --dev bash -c "cd dangerzone && ./install/linux/build-deb.py"
```

Publish the .deb under `./deb_dist` to the
[`freedomofpress/apt-tools-prod`](https://github.com/freedomofpress/apt-tools-prod)
repo, by sending a PR. Follow the instructions in that repo on how to do so.

#### Fedora

> **NOTE**: This procedure will have to be done for every supported Fedora version.
>
> In this section, Fedora 41 is used as an example.

Create a Fedora development environment. [Follow the
instructions in the build section](https://github.com/freedomofpress/dangerzone/blob/main/BUILD.md#fedora),
or create it locally with:

```bash
./dev_scripts/env.py --distro fedora --version 41 build-dev
./dev_scripts/env.py --distro fedora --version 41 run --dev bash

# Get the vendorized assets
poetry run mazette install

# Retrieve the latest container
poetry run ./dev_scripts/dangerzone-image prepare-archive
    --image ghcr.io/freedomofpress/dangerzone/v1@sha256:${DIGEST}
    --output share/container.tar

# Create a .rpm:
./dev_scripts/env.py --distro fedora --version 41 run --dev bash -c "cd dangerzone && ./install/linux/build-rpm.py"
```

Publish the .rpm under `./dist` to the
[`freedomofpress/yum-tools-prod`](https://github.com/freedomofpress/yum-tools-prod) repo, by sending a PR. Follow the instructions in that repo on how to do so.

#### Qubes

Create a `.rpm` for Qubes:

```sh
./dev_scripts/env.py --distro fedora --version 41 run --dev bash -c "cd dangerzone && ./install/linux/build-rpm.py --qubes"
```

and similarly publish it to the [`freedomofpress/yum-tools-prod`](https://github.com/freedomofpress/yum-tools-prod) repo.
