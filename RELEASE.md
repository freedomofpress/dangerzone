# Release instructions

This section documents the release process. Unless you're a dangerzone developer making a release, you'll probably never need to follow it.

## Changelog, version, and signed git tag

Before making a release, all of these should be complete:

* Update `version` in `pyproject.toml`
* Update `dangerzone_version` in `dangerzone/__init__.py`
* Update version and download links in `README.md`
* CHANGELOG.md should be updated to include a list of all major changes since the last release
* There must be a PGP-signed git tag for the version, e.g. for dangerzone 0.1.0, the tag must be `v0.1.0`

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
  - Apple-trusted `Developer ID Application: FIRST LOOK PRODUCTIONS, INC.` and `Developer ID Installer: FIRST LOOK PRODUCTIONS, INC.` code-signing certificates installed
  - An app-specific Apple ID password saved in the login keychain called `flockagent-notarize`
- Verify and checkout the git tag for this release
- Run `poetry install`
- Run `poetry run ./install/macos/build_app.py --with-codesign`; this will make `dist/Dangerzone.dmg`
- Notarize it: `xcrun altool --notarize-app --primary-bundle-id "media.firstlook.dangerzone" -u "micah@firstlook.org" -p "@keychain:dangerzone-notarize" --file dist/Dangerzone $VERSION.dmg`
- Wait for it to get approved, check status with: `xcrun altool --notarization-history 0 -u "micah@firstlook.org" -p "@keychain:dangerzone-notarize"`
- (If it gets rejected, you can see why with: `xcrun altool --notarization-info [RequestUUID] -u "micah@firstlook.org" -p "@keychain:dangerzone-notarize"`)
- After it's approved, staple the ticket: `xcrun stapler staple dist/Dangerzone $VERSION.dmg`

This process ends up with the final file:

```
dist/Dangerzone $VERSION.dmg
```

## Windows release

To make a Windows release, go to the Windows build machine:

- Build machine should be running Windows 10, and have the Windows codesigning certificate installed
- Verify and checkout the git tag for this release
- Run `poetry install`
- Run `poetry shell`, then `cd ..\pyinstaller`, `python setup.py install`, `exit`
- Run `poetry run install\windows\step1-build-exe.bat`
- Open a second command prompt _as an administratror_, cd to the dangerzone directory, and run: `install\windows\step2-make-symlink.bat`
- Back in the first command prompt, run: `poetry run install\windows\step3-build-installer.bat`
- When you're done you will have `dist\Dangerzone.msi`

Rename `Dangerzone.msi` to `Dangerzone $VERSION.msi`.

## Linux release

Linux binaries are automatically built and deployed to repositories when a new tag is pushed.

## Publishing the release

To publish the release:

- Create a new release on GitHub, put the changelog in the description of the release, and upload the macOS and Windows installers