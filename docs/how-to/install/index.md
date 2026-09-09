---
hide:
  - toc
---

# Install

Pick your operating system to see how to install Dangerzone:

=== "macOS"

    <span id="macos"></span>
    

    <!-- [[[cog
    from docs_cog import download_links
    download_links(
        ("Mac (Apple Silicon CPU)", "Dangerzone-{version}-arm64.dmg"),
        ("Mac (Intel CPU)", "Dangerzone-{version}-i686.dmg"),
        indent=4,
    )
    ]]] -->

    - Download [Dangerzone 0.11.0 for Mac (Apple Silicon CPU)](https://github.com/freedomofpress/dangerzone/releases/download/v0.11.0/Dangerzone-0.11.0-arm64.dmg)
    - Download [Dangerzone 0.11.0 for Mac (Intel CPU)](https://github.com/freedomofpress/dangerzone/releases/download/v0.11.0/Dangerzone-0.11.0-i686.dmg)
    <!-- [[[end]]] -->

    You can also install Dangerzone for Mac using [Homebrew](https://brew.sh/): `brew install --cask dangerzone`
    
    ??? info "See which versions of macOS are supported"
        We support the releases of macOS that are within Apple's servicing timeline, usually meaning security updates for the latest 3 releases.

=== "Windows"

    <span id="windows"></span>

    <!-- [[[cog
    from docs_cog import download_links
    download_links(("Windows", "Dangerzone-{version}.msi"), indent=4)
    ]]] -->

    - Download [Dangerzone 0.11.0 for Windows](https://github.com/freedomofpress/dangerzone/releases/download/v0.11.0/Dangerzone-0.11.0.msi)
    <!-- [[[end]]] -->

    You can also install Dangerzone for Windows using [Winget](https://learn.microsoft.com/windows/package-manager/):

    ```
    winget install FreedomofthePressFoundation.Dangerzone
    ```

    ??? info "See which versions of Windows are supported"

        We generally support Windows releases that are within [Microsoft’s servicing timeline](https://support.microsoft.com/en-us/help/13853/windows-lifecycle-fact-sheet). That means that a recent release of Windows 10 or Windows 11 is required. In addition, you need to have hardware virtualization enabled (to be more specific, on x64, WSL requires build 18362 or later, and 19041 or later is required for arm64 systems).
=== "Ubuntu, Debian"

    <span id="ubuntu-debian"></span>

    ??? info "See the list of supported Debian and Ubuntu versions"
        Dangerzone is available for:
    
        - Ubuntu 26.04 (resolute)
        - Ubuntu 25.10 (questing)
        - Ubuntu 24.04 (noble)
        - Ubuntu 22.04 (jammy)
        - Debian 14 (forky)
        - Debian 13 (trixie)
        - Debian 12 (bookworm)
      
        Our "support rule" is that we support Ubuntu and Debian releases that are still within their respective servicing timelines, with a few twists:

        - Ubuntu: We follow upstream support with an extra cutoff date. No support for versions prior to the second oldest LTS release.
        - Debian: We support the last two stable releases.

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

        This section follows the official instructions on configuring [third-party Debian repos](https://wiki.debian.org/DebianRepository/UseThirdParty).

        To mitigate a class of attacks against our APT repo (e.g., injecting packages signed with an attacker key), we add an additional step in our instructions to verify the downloaded GPG key against its fingerprint.

=== "Fedora"

    <span id="fedora"></span>

    ??? info "See the list of supported Fedora versions"
        Dangerzone is available for:
    
        - Fedora 44
        - Fedora 43

        *We support Fedora releases that are still within their servicing timeline (we follow upstream support).*


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

    #### Fedora Atomic (Silverblue, Kinoite, etc.)

    !!! warning

        This distribution is [not officially supported](../../reference/supported-platforms.md#note-on-unsupported-linux-distros) by the Dangerzone team. Please, proceed at your own risks, only if you know what you're doing.

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

=== "Qubes OS"

    <span id="qubes-os"></span>

    !!! warning "Qubes support is still in beta"

        This section is for the beta version of native Qubes support. If you want to try out the stable Dangerzone version (which uses containers instead of virtual machines for isolation), please follow the Fedora or Debian instructions and adapt them as needed.

        If you followed these instructions before October 25, 2023, please read [this security advisory](../../advisories/2023-10-25.md). This notice will be removed with the 1.0.0 release of Dangerzone.

    !!! important "You might want to use a different template"

        This section will install Dangerzone in your **default template** (`fedora-43` as of writing this). If you want to install it in a different one, make sure to replace `fedora-43` with the template of your choice.

    The following steps must be completed once. Make sure you run them in the specified qubes.

    Overview of the qubes you'll create:

    | qube   | type     | purpose                                                |
    | ------ | -------- | ------------------------------------------------------ |
    | dz-dvm | app qube | offline disposable template for performing conversions |

    #### In `dom0`:

    Create a **disposable**, offline app qube (`dz-dvm`), based on your default template. This will be the qube where the documents will be sanitized:

    ```sh
    qvm-create --class AppVM --label red --template fedora-43 \
        --prop netvm="" --prop template_for_dispvms=True \
        --prop default_dispvm='' dz-dvm
    ```

    Add an RPC policy (`/etc/qubes/policy.d/50-dangerzone.policy`) that will allow launching a disposable qube (`dz-dvm`) when Dangerzone converts a document, with the following contents:

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

    While Dangerzone gets installed, you will be prompted to accept a signing key. Expand the instructions in the [Verifying Dangerzone GPG key](#verifying-dangerzone-gpg-key) section to verify the key.

    Finally, shutdown the template and restart the qubes where you want to use Dangerzone in. Go to "Qube Settings" -> choose the "Applications" tab, click on "Refresh applications", and then move "Dangerzone" from the "Available" column to "Selected".

    You can now launch Dangerzone from the list of applications for your qube, and pass it a file to sanitize.

=== "Tails"

    <span id="tails"></span>

    You can follow [installation instructions on the Tails documentation](https://tails.net/doc/persistent_storage/additional_software/dangerzone/index.en.html) to install Dangerzone on Tails (it is not included by default, at least for now.)

*You can read more about the supported platforms [on the dedicated section](../../reference/supported-platforms.md).*
