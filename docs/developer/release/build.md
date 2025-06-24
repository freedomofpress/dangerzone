# Build release artifacts

Follow the sections below, depending on the OS you want to build artifacts for.
Note that you can build Linux artifacts from macOS, since we use containers to
do so.

We suggest following the automated instructions to build things quicker. For an
explanation of what they do under the hood, read
[`docs/developer/doit.md`](../doit.md).

## macOS

### Automated

You can automate these steps from your macOS terminal app with:

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
    --image ghcr.io/freedomofpress/dangerzone/dangerzone@sha256:${DIGEST}
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

## Windows

- [ ] Checkout the dependencies, and clean your local copy:

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

- [ ] Copy the container image into the VM
- [ ] Download the necessary assets with `poetry run mazette install`
- [ ] Run `poetry run .\install\windows\build-app.bat`
- [ ] When you're done you will have `dist\Dangerzone.msi`

Rename `Dangerzone.msi` to `Dangerzone-$VERSION.msi`.

## Linux

### Automated

You can automate the manual steps from any Linux distribution:

- [ ] Run `make build-linux` (not necessary if you've previously built artifacts for macOS)

### Manual steps

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
poetry run ./dev_scripts/dangerzone-image prepare-archive
    --image ghcr.io/freedomofpress/dangerzone/dangerzone@sha256:${DIGEST}
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
> In this section, we'll use Fedora 41 as an example.

Create a Fedora development environment. You can [follow the
instructions in our build section](https://github.com/freedomofpress/dangerzone/blob/main/BUILD.md#fedora),
or create your own locally with:

```sh
./dev_scripts/env.py --distro fedora --version 41 build-dev

poetry run ./dev_scripts/dangerzone-image prepare-archive
    --image ghcr.io/freedomofpress/dangerzone/dangerzone@sha256:${DIGEST}
    --output share/container.tar

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

and similarly publish it to the [`freedomofpress/yum-tools-prod`](https://github.com/freedomofpress/yum-tools-prod) repo.
