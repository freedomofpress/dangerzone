# Prepare build environments

## macOS

### Initial setup

- Ensure that the build machine has:
  - Apple-trusted `Developer ID Application: Freedom of the Press Foundation (94ZZGGGJ3W)` code-signing certificates installed
- Apple account must have:
  - A valid application password for `notarytool` in the Keychain. You can
    verify this by running:

    ```bash
    xcrun notarytool history --apple-id "<email>" --keychain-profile "dz-notarytool-release-key"
    ```

    If they key isn't found, add it to the Keychain by running:

    ```bash
    xcrun notarytool store-credentials dz-notarytool-release-key --apple-id <email> --team-id 94ZZGGGJ3W
    ```

    with the respective `email`. The team ID is retrieved from
    https://developer.apple.com -> Account -> Membership details -> Team ID.

### On each release

- [ ] Agree to any new terms and conditions in https://developer.apple.com, once you login with FPF's Apple ID.
- [ ] Upgrade "Command Line Tools" from "System Settings -> Software Update", from an account with admin privileges.
- [ ] Upgrade Xcode from the App Store, from an account with admin privileges.
- [ ] Update Docker Desktop and Podman Desktop to the latest versions.
- [ ] Update Python to the latest supported version, following our [instructions](../python.md)

## Windows

The Windows release is performed in a Windows 11 virtual machine (as opposed to a physical one).

### Initial Setup

- Download a VirtualBox VM image for Windows from here: https://developer.microsoft.com/en-us/windows/downloads/virtual-machines/ and import it into VirtualBox. Also install the Oracle VM VirtualBox Extension Pack.
- Install updates
- Install git for Windows from https://git-scm.com/download/win, and clone the dangerzone repo
- Follow the Windows build instructions in [`BUILD.md`](https://github.com/freedomofpress/dangerzone/blob/main/BUILD.md#windows), except:
  - Don't install Docker Desktop (it won't work without nested virtualization)
  - Install the Windows SDK from here: https://developer.microsoft.com/en-us/windows/downloads/windows-sdk/ and add `C:\Program Files (x86)\Microsoft SDKs\ClickOnce\SignTool` to the path (you'll need it for `signtool.exe`)
  - You'll also need the Windows codesigning certificate installed on the VM

### On each release

- [ ] Update WiX, if necessary
- [ ] Update Python to the latest supported version, following our [instructions](../python.md)
