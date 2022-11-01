# Release instructions

This section documents the release process. Unless you're a dangerzone developer making a release, you'll probably never need to follow it.

## Changelog, version, and signed git tag

Before making a release, all of these should be complete:

- [ ] Update `version` in `pyproject.toml`
- [ ] Update `share/version.txt`
- [ ] Update version and download links in `README.md`, and screenshot if necessary
- [ ] CHANGELOG.md should be updated to include a list of all major changes since the last release
- [ ] In `.circleci/config.yml`, add new platforms and remove obsolete platforms
- [ ] Create a test build in Windows and make sure it works
- [ ] Create a test build in macOS and make sure it works
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
  - macOS 10.14
  - Apple-trusted `Developer ID Application: FIRST LOOK PRODUCTIONS, INC. (P24U45L8P5)` code-signing certificates installed
- Verify and checkout the git tag for this release
- Run `poetry install`
- Run `poetry run ./install/macos/build-app.py --with-codesign`; this will make `dist/Dangerzone.dmg`
- Notarize it: `xcrun altool --notarize-app --primary-bundle-id "media.firstlook.dangerzone" -u "micah@firstlook.org" -p "$PASSWORD" --file dist/Dangerzone.dmg`
- Wait for it to get approved, check status with: `xcrun altool --notarization-history 0 -u "micah@firstlook.org" -p "$PASSWORD"`
- (If it gets rejected, you can see why with: `xcrun altool --notarization-info $REQUEST_UUID -u "micah@firstlook.org" -p "$PASSWORD"`)
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

Linux binaries are automatically built and deployed to repositories when a new tag is pushed.

## Publishing the release

To publish the release:

- Create a new release on GitHub, put the changelog in the description of the release, and upload the macOS and Windows installers
- Update the [Installing Dangerzone](INSTALL.md) page
- Update the [Dangerzone website](https://github.com/firstlookmedia/dangerzone.rocks) to link to the new installers
- Update the brew cask release of Dangerzone with a [PR like this one](https://github.com/Homebrew/homebrew-cask/pull/116319)
