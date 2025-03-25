# Install Dangerzone

## MacOS

- Download [Dangerzone 0.8.1 for Mac (Apple Silicon CPU)](https://github.com/freedomofpress/dangerzone/releases/download/v0.8.1/Dangerzone-0.8.1-arm64.dmg)
- Download [Dangerzone 0.8.1 for Mac (Intel CPU)](https://github.com/freedomofpress/dangerzone/releases/download/v0.8.1/Dangerzone-0.8.1-i686.dmg)

You can also install Dangerzone for Mac using [Homebrew](https://brew.sh/):

```bash
brew install --cask dangerzone
```


:::{note}

You will also need to install [Docker Desktop](https://www.docker.com/products/docker-desktop/).
This program needs to run alongside Dangerzone at all times, since it is what allows Dangerzone to
create the secure environment.

:::

## Windows

- Download [Dangerzone 0.8.1 for Windows](https://github.com/freedomofpress/dangerzone/releases/download/v0.8.1/Dangerzone-0.8.1.msi)

:::{note}

You will also need to install [Docker Desktop](https://www.docker.com/products/docker-desktop/).
This program needs to run alongside Dangerzone at all times, since it is what allows Dangerzone to
create the secure environment.

:::

## Linux

On Linux, Dangerzone uses [Podman](https://podman.io/) instead of Docker Desktop for creating
an isolated environment. It will be installed automatically when installing Dangerzone.

Dangerzone is available for:
- Ubuntu 25.04 (plucky)
- Ubuntu 24.10 (oracular)
- Ubuntu 24.04 (noble)
- Ubuntu 22.04 (jammy)
- Debian 13 (trixie)
- Debian 12 (bookworm)
- Debian 11 (bullseye)
- Fedora 41
- Fedora 40
- Tails
- Qubes OS (beta support)

### Ubuntu, Debian

:::{admonition} Backport notice for Ubuntu 22.04 (Jammy) users regarding the `conmon` package
:collapsible: closed

The `conmon` version that Podman uses and Ubuntu Jammy ships, has a bug that gets triggered by Dangerzone (more details in https://github.com/freedomofpress/dangerzone/issues/685). To fix this, we provide our own `conmon` package through our APT repo, which was built with the following [instructions](https://github.com/freedomofpress/maint-dangerzone-conmon/tree/ubuntu/jammy/fpf).

This package is essentially a backport of the `conmon` package [provided](https://packages.debian.org/source/oldstable/conmon) by Debian Bullseye.
:::

First, retrieve the PGP keys.

Starting with Trixie, follow these instructions to download the PGP keys:

```bash
sudo apt-get update && sudo apt-get install sq -y
mkdir -p /etc/apt/keyrings/
sq network keyserver \
   --server hkps://keys.openpgp.org \
   search "DE28 AB24 1FA4 8260 FAC9 B8BA A7C9 B385 2260 4281" \
   --output /etc/apt/keyrings/fpf-apt-tools-archive-keyring.gpg
```

On other Debian-derivatives:

```sh
sudo apt-get update && sudo apt-get install gnupg2 ca-certificates -y
gpg --keyserver hkps://keys.openpgp.org \
    --no-default-keyring --keyring ./fpf-apt-tools-archive-keyring.gpg \
    --recv-keys "DE28 AB24 1FA4 8260 FAC9 B8BA A7C9 B385 2260 4281"
sudo mkdir -p /etc/apt/keyrings/
sudo gpg --no-default-keyring --keyring ./fpf-apt-tools-archive-keyring.gpg \
    --armor --export "DE28 AB24 1FA4 8260 FAC9 B8BA A7C9 B385 2260 4281" \
    > /etc/apt/keyrings/fpf-apt-tools-archive-keyring.gpg
```

Then, on all distributions, add the URL of the repo in your APT sources:

```sh
. /etc/os-release
echo "deb [signed-by=/etc/apt/keyrings/fpf-apt-tools-archive-keyring.gpg] \
    https://packages.freedom.press/apt-tools-prod ${VERSION_CODENAME?} main" \
    | sudo tee /etc/apt/sources.list.d/fpf-apt-tools.list
```

Install Dangerzone:

```
sudo apt update
sudo apt install -y dangerzone
```

:::{admonition} Security notice on third-party Debian repos</i></summary>
:collapsible: closed

This section follows the official instructions on configuring [third-party
Debian repos](https://wiki.debian.org/DebianRepository/UseThirdParty).

To mitigate a class of attacks against our APT repo (e.g., injecting packages
signed with an attacker key), we add an additional step in our instructions to
verify the downloaded GPG key against its fingerprint.

Aside from these protections, the user needs to be aware that Debian packages
run as `root` during the installation phase, so they need to place some trust
on our signed Debian packages. This holds for any third-party Debian repo.
:::

### Fedora

Type the following commands in a terminal:

```
sudo dnf install 'dnf-command(config-manager)'
sudo dnf-3 config-manager --add-repo=https://packages.freedom.press/yum-tools-prod/dangerzone/dangerzone.repo
sudo dnf install dangerzone
```

##### Verifying Dangerzone GPG key

:::{admonition} Importing GPG key 0x22604281: ... Is this ok [y/N]:
:collapsible: closed

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
:::

:::{note}
If it does not show this fingerprint confirmation or the fingerprint does not match, it is possible that our servers were compromised. Be distrustful and reach out to us.
:::

The `Fingerprint` should be `DE28 AB24 1FA4 8260 FAC9 B8BA A7C9 B385 2260 4281`. For extra security, you should confirm it matches the one at the bottom of our website ([dangerzone.rocks](https://dangerzone.rocks)) and our [Mastodon account](https://fosstodon.org/@dangerzone) bio.

After confirming that it matches, type `y` (for yes) and the installation should proceed.

### Qubes OS

:::{warning}
This section is for the beta version of native Qubes support. If you
want to try out the stable Dangerzone version (which uses containers instead
of virtual machines for isolation), please follow the Fedora or Debian
instructions and adapt them as needed.
**If you followed these instructions before October 25, 2023, please read [this security advisory](docs/advisories/2023-10-25.md).**
This notice will be removed with the 1.0.0 release of Dangerzone.
:::

:::{important}
This section will install Dangerzone in your **default template**
(`fedora-40` as of writing this). If you want to install it in a different
one, make sure to replace `fedora-40` with the template of your choice.
:::

The following steps must be completed once. Make sure you run them in the
specified qubes.

Overview of the qubes you'll create:

| qube         |   type   | purpose |
|--------------|----------|---------|
| dz-dvm       | app qube | offline disposable template for performing conversions |

#### In `dom0`:

Create a **disposable**, offline app qube (`dz-dvm`), based on your default
template. This will be the qube where the documents will be sanitized:

```
qvm-create --class AppVM --label red --template fedora-40 \
    --prop netvm="" --prop template_for_dispvms=True \
    --prop default_dispvm='' dz-dvm
```

Add an RPC policy (`/etc/qubes/policy.d/50-dangerzone.policy`) that will
allow launching a disposable qube (`dz-dvm`) when Dangerzone converts a
document, with the following contents:

```
dz.Convert         *       @anyvm       @dispvm:dz-dvm  allow
```

#### In the `fedora-40` template

Install Dangerzone:

```
sudo dnf-3 config-manager --add-repo=https://packages.freedom.press/yum-tools-prod/dangerzone/dangerzone.repo
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

If you'd like to build from source, follow the [build instructions](build.md).

## Verifying PGP signatures

You can verify that the package you download is legitimate and hasn't been
tampered with by verifying its PGP signature. For Windows and macOS, this step
is optional and provides defense in depth: the Dangerzone binaries include
operating system-specific signatures, and you can just rely on those alone if
you'd like.

### Obtaining signing key

Our binaries are signed with a PGP key owned by Freedom of the Press Foundation:
* Name: Dangerzone Release Key
* PGP public key fingerprint `DE28 AB24 1FA4 8260 FAC9 B8BA A7C9 B385 2260 4281`
  - You can download this key [from the keys.openpgp.org keyserver](https://keys.openpgp.org/vks/v1/by-fingerprint/DE28AB241FA48260FAC9B8BAA7C9B38522604281).

_(You can also cross-check this fingerprint with the fingerprint in our
[Mastodon page](https://fosstodon.org/@dangerzone) and the fingerprint in the
footer of our [official site](https://dangerzone.rocks))_

You must have GnuPG installed to verify signatures. For macOS you probably want
[GPGTools](https://gpgtools.org/), and for Windows you probably want
[Gpg4win](https://www.gpg4win.org/).

### Signatures

Our [GitHub Releases page](https://github.com/freedomofpress/dangerzone/releases)
hosts the following files:
* Windows installer (`Dangerzone-<version>.msi`)
* macOS archives (`Dangerzone-<version>-<arch>.dmg`)
* Container images (`container-<version>-<arch>.tar`)
* Source package (`dangerzone-<version>.tar.gz`)

All these files are accompanied by signatures (as `.asc` files). We'll explain
how to verify them below, using `0.6.1` as an example.

### Verifying

Once you have imported the Dangerzone release key into your GnuPG keychain,
downloaded the binary and ``.asc`` signature, you can verify the binary in a
terminal like this:

For the Windows binary:

```
gpg --verify Dangerzone-0.6.1.msi.asc Dangerzone-0.6.1.msi
```

For the macOS binaries (depending on your architecture):

```
gpg --verify Dangerzone-0.6.1-arm64.dmg.asc Dangerzone-0.6.1-arm64.dmg
gpg --verify Dangerzone-0.6.1-i686.dmg.asc Dangerzone-0.6.1-i686.dmg
```

For the container images:

```
gpg --verify container-0.6.1-i686.tar.asc container-0.6.1-i686.tar
```

For the source package:

```
gpg --verify dangerzone-0.6.1.tar.gz.asc dangerzone-0.6.1.tar.gz
```

We also hash all the above files with SHA-256, and provide a list of these
hashes as a separate file (`checksums-0.6.1.txt`). This file is signed as well,
and the signature is embedded within it. You can download this file and verify
it with:

```
gpg --verify checksums.txt
```

The expected output looks like this:

```
gpg: Signature made Mon Apr 22 09:29:22 2024 PDT
gpg:                using RSA key 04CABEB5DD76BACF2BD43D2FF3ACC60F62EA51CB
gpg: Good signature from "Dangerzone Release Key <dangerzone-release-key@freedom.press>" [unknown]
gpg: WARNING: This key is not certified with a trusted signature!
gpg:          There is no indication that the signature belongs to the owner.
Primary key fingerprint: DE28 AB24 1FA4 8260 FAC9  B8BA A7C9 B385 2260 4281
     Subkey fingerprint: 04CA BEB5 DD76 BACF 2BD4  3D2F F3AC C60F 62EA 51CB
```

If you don't see `Good signature from`, there might be a problem with the
integrity of the file (malicious or otherwise), and you should not install the
package.

The `WARNING:` shown above, is not a problem with the package, it only means you
haven't defined a level of "trust" for Dangerzone's PGP key.

If you want to learn more about verifying PGP signatures, the guides for
[Qubes OS](https://www.qubes-os.org/security/verifying-signatures/) and the
[Tor Project](https://support.torproject.org/tbb/how-to-verify-signature/) may
be useful.
