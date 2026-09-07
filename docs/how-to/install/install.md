# Installation

## MacOS

- Download [Dangerzone 0.11.0 for Mac (Apple Silicon CPU)](https://github.com/freedomofpress/dangerzone/releases/download/v0.11.0/Dangerzone-0.11.0-arm64.dmg)
- Download [Dangerzone 0.11.0 for Mac (Intel CPU)](https://github.com/freedomofpress/dangerzone/releases/download/v0.11.0/Dangerzone-0.11.0-i686.dmg)

!!! tip

    We support the releases of macOS that are still within Apple's servicing timeline, usually meaning 
    security updates for the latest 3 releases.

You can also install Dangerzone for Mac using [Homebrew](https://brew.sh/): `brew install --cask dangerzone`

## Windows

- Download [Dangerzone 0.11.0 for Windows](https://github.com/freedomofpress/dangerzone/releases/download/v0.11.0/Dangerzone-0.11.0.msi)

!!! tip

    We generally support Windows releases that are still within [Microsoft’s servicing timeline](https://support.microsoft.com/en-us/help/13853/windows-lifecycle-fact-sheet). That means that a recent release of Windows 10 or Windows 11 is required. In addition, you need to have hardware virtualization enabled (to be more specific, on x64, WSL requires build 18362 or later, and 19041 or later is required for arm64 systems).

You can also install Dangerzone for Windows using [Winget](https://learn.microsoft.com/windows/package-manager/): `winget install FreedomofthePressFoundation.Dangerzone`

## Linux

!!! tip

    We support Ubuntu, Debian, and Fedora releases that are still within
    their respective servicing timelines, with a few twists:

    - Ubuntu: We follow upstream support with an extra cutoff date. No support for
      versions prior to the second oldest LTS release.
    - Fedora: We follow upstream support.
    - Debian: We support the last two stable releases.

Dangerzone is available for:

- Ubuntu 26.04 (resolute)
- Ubuntu 25.10 (questing)
- Ubuntu 24.04 (noble)
- Ubuntu 22.04 (jammy)
- Debian 14 (forky)
- Debian 13 (trixie)
- Debian 12 (bookworm)
- Fedora 44
- Fedora 43
- Tails
- Qubes OS (beta support)

### Ubuntu, Debian

??? info "Backport notice for Ubuntu 22.04 (Jammy) users regarding the `conmon` package"

    The `conmon` version that Podman uses and Ubuntu Jammy ships, has a bug
    that gets triggered by Dangerzone
    (more details in https://github.com/freedomofpress/dangerzone/issues/685).
    To fix this, we provide our own `conmon` package through our APT repo, which
    was built with the following [instructions](https://github.com/freedomofpress/maint-dangerzone-conmon/tree/ubuntu/jammy/fpf).
    This package is essentially a backport of the `conmon` package
    [provided](https://packages.debian.org/source/oldstable/conmon) by Debian
    Bullseye.

Add our repository following these instructions:

Download the GPG key for the repo:

```sh
sudo apt-get update && sudo apt-get install -y gpg ca-certificates
sudo mkdir -p /etc/apt/keyrings
sudo gpg --keyserver hkps://keys.openpgp.org \
    --no-default-keyring --no-permission-warning --homedir $(mktemp -d) \
    --keyring gnupg-ring:/etc/apt/keyrings/fpf-apt-tools-archive-keyring.gpg \
    --recv-keys DE28AB241FA48260FAC9B8BAA7C9B38522604281
sudo chmod +r /etc/apt/keyrings/fpf-apt-tools-archive-keyring.gpg
```

Add the URL of the repo in your APT sources:

```sh
. /etc/os-release
echo "deb [signed-by=/etc/apt/keyrings/fpf-apt-tools-archive-keyring.gpg] \
    https://packages.freedom.press/apt-tools-prod ${VERSION_CODENAME?} main" \
    | sudo tee /etc/apt/sources.list.d/fpf-apt-tools.list
```

Install Dangerzone:

```sh
sudo apt update
sudo apt install -y dangerzone

# Alternatively, use dangerzone-full if you prefer to install dangerzone
# with its container bundled (larger package, but no download at first use)
sudo apt install -y dangerzone-full
```

??? note "Expand this section for a security notice on third-party Debian repos"

    This section follows the official instructions on configuring [third-party
    Debian repos](https://wiki.debian.org/DebianRepository/UseThirdParty).

    To mitigate a class of attacks against our APT repo (e.g., injecting packages
    signed with an attacker key), we add an additional step in our instructions to
    verify the downloaded GPG key against its fingerprint.

### Fedora

Type the following commands in a terminal:

```sh
sudo dnf install 'dnf-command(config-manager)'
sudo dnf config-manager addrepo --from-repofile=https://packages.freedom.press/yum-tools-prod/dangerzone/dangerzone.repo
sudo dnf install dangerzone

# Alternatively, use dangerzone-full if you prefer to install dangerzone
# with its container bundled (larger package, but no download at first use)
sudo dnf install dangerzone-full
```

##### Verifying Dangerzone GPG key

??? note "Importing GPG key 0x22604281: ... Is this ok [y/N]:"

    After some minutes of running the above command (depending on your internet speed) you'll be asked to confirm the fingerprint of our signing key. This is to make sure that in the case our servers are compromised your computer stays safe. It should look like this:

    ```console
    --------------------------------------------------------------------------------
    Total                                           389 kB/s | 732 MB     32:07
    Dangerzone repository                           3.8 MB/s | 3.8 kB     00:00
    Importing GPG key 0x22604281:
     Userid     : "Dangerzone Release Key <dangerzone-release-key@freedom.press>"
     Fingerprint: DE28 AB24 1FA4 8260 FAC9 B8BA A7C9 B385 2260 4281
     From       : /etc/pki/rpm-gpg/RPM-GPG-dangerzone.pub
    Is this ok [y/N]:
    ```

    > **Note**: If it does not show this fingerprint confirmation or the fingerprint does not match, it is possible that our servers were compromised. Be distrustful and reach out to us.

    The `Fingerprint` should be `DE28 AB24 1FA4 8260 FAC9 B8BA A7C9 B385 2260 4281`. For extra security, you should confirm it matches the one at the bottom of our website ([dangerzone.rocks](https://dangerzone.rocks)) and our [Mastodon account](https://fosstodon.org/@dangerzone) bio.

    After confirming that it matches, type `y` (for yes) and the installation should proceed.

### Fedora Atomic (Silverblue, Kinoite, etc.)

!!! warning

    This distribution is [not officially supported](../reference/supported-platforms.md#note-on-unsupported-linux-distros)
    by the Dangerzone team. Please, proceed at your own risks,
    only if you know what you're doing.

Type the following commands in a terminal:

```sh
curl -o - https://packages.freedom.press/yum-tools-prod/dangerzone/dangerzone.repo \
    | sudo tee /etc/yum.repos.d/dangerzone.repo > /dev/null
rpm-ostree install dangerzone
# Alternatively, use dangerzone-full if you prefer to install dangerzone
# with its container bundled (larger package, but no download at first use)
rpm-ostree install dangerzone-full
```

After the above command completes, restart your computer to complete the installation.

### Qubes OS

!!! warning

    This section is for the beta version of native Qubes support. If you
    want to try out the stable Dangerzone version (which uses containers instead
    of virtual machines for isolation), please follow the Fedora or Debian
    instructions and adapt them as needed.

    **If you followed these instructions before October 25, 2023, please read [this security advisory](../advisories/2023-10-25.md).**
    This notice will be removed with the 1.0.0 release of Dangerzone.


!!! important

    This section will install Dangerzone in your **default template**
    (`fedora-43` as of writing this). If you want to install it in a different
    one, make sure to replace `fedora-43` with the template of your choice.

The following steps must be completed once. Make sure you run them in the
specified qubes.

Overview of the qubes you'll create:

| qube         |   type   | purpose |
|--------------|----------|---------|
| dz-dvm       | app qube | offline disposable template for performing conversions |

#### In `dom0`:

Create a **disposable**, offline app qube (`dz-dvm`), based on your default
template. This will be the qube where the documents will be sanitized:

```sh
qvm-create --class AppVM --label red --template fedora-43 \
    --prop netvm="" --prop template_for_dispvms=True \
    --prop default_dispvm='' dz-dvm
```

Add an RPC policy (`/etc/qubes/policy.d/50-dangerzone.policy`) that will
allow launching a disposable qube (`dz-dvm`) when Dangerzone converts a
document, with the following contents:

```
dz.Convert         *       @anyvm       @dispvm:dz-dvm  allow
```

#### In the `fedora-43` template

Install Dangerzone:

```sh
sudo dnf install 'dnf-command(config-manager)'
sudo dnf config-manager addrepo --from-repofile=https://packages.freedom.press/yum-tools-prod/dangerzone/dangerzone.repo
sudo dnf install dangerzone-qubes
```

While Dangerzone gets installed, you will be prompted to accept a signing key.
Expand the instructions in the [Verifying Dangerzone GPG key](#verifying-dangerzone-gpg-key)
section to verify the key.

Finally, shutdown the template and restart the qubes where you want to use
Dangerzone in. Go to "Qube Settings" -> choose the "Applications" tab,
click on "Refresh applications", and then move "Dangerzone" from the "Available"
column to "Selected".

You can now launch Dangerzone from the list of applications for your qube, and
pass it a file to sanitize.

## Tails

Dangerzone is not yet available by default in Tails, but we have collaborated
with the Tails team to offer manual
[installation instructions](https://tails.net/doc/persistent_storage/additional_software/dangerzone/index.en.html)
for Tails users.

## Build from source

If you'd like to build from source, follow the [build instructions](build-from-source.md).

## Installing a previous version

Sometimes you need an older Dangerzone, for example to reproduce a bug or
because the latest release doesn't work on your machine yet. This guide
explains where old versions are and how to install them.

!!! warning

    Older versions carry older sandbox images, with known vulnerabilities
    that later releases fixed. Use them for testing, and go back to the
    latest release as soon as you can. See
    [Update Dangerzone](update-dangerzone.md).

### macOS and Windows

Every release is kept on the
[GitHub releases page](https://github.com/freedomofpress/dangerzone/releases),
with its `.dmg` and `.msi` installers, their PGP signatures, and a signed
checksums file. Pick the version you need, download the installer for your
platform, [verify its signature](verify-pgp-signatures.md), and run it.

Installing an older version over a newer one works on both platforms. Your
settings are kept. Homebrew and Winget only offer the latest release, so use
the installers from the releases page for older versions.

### Linux

Our APT and RPM repositories only serve the latest release: older packages
are pruned when a new version is published, to keep the repositories
manageable. There are two ways to get an older version:

#### Build the package from the release tag

Each release is tagged in git (`v0.10.0`, `v0.11.0`, and so on). Check out
the tag and build the `.deb` or `.rpm` by following the
[build from source](build-from-source.md#debianubuntu) guides for that
version:

```sh
git clone https://github.com/freedomofpress/dangerzone/
cd dangerzone
git checkout v0.10.0
# Follow BUILD.md of that version, then for example:
./install/linux/build-deb.py
```

Read the `BUILD.md` of the checked-out tag. The steps change between
versions, so the current documentation may not apply.

#### Use the source tarball

The GitHub releases page also hosts a signed source archive
(`dangerzone-<version>.tar.gz`) for every release, if you prefer not to use
git.

### Qubes OS and Tails

Follow the Linux instructions above in the template (Qubes OS) or refer to
the [Tails documentation](https://tails.net/doc/persistent_storage/additional_software/dangerzone/index.en.html).
