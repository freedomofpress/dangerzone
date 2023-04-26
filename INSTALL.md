Dangerzone is available for:

- Ubuntu 22.10 (kinetic)
- Ubuntu 22.04 (jammy)
- Ubuntu 20.04 (focal)
- Debian 12 (bookworm)
- Debian 11 (bullseye)
- Fedora 38
- Fedora 37
- Fedora 36

### Ubuntu, Debian

<details>
  <summary><i>:memo: Expand this section if you are on Ubuntu 20.04 (Focal).</i></summary>
  </br>

  Dangerzone requires [Podman](https://podman.io/), which is not available
  through the official Ubuntu Focal repos. To proceed with the Dangerzone
  installation, you need to add an extra OpenSUSE repo that provides Podman to
  Ubuntu Focal users. You can follow the instructions below, which have been
  copied from the [official Podman blog](https://podman.io/new/2021/06/16/new.html):

  ```bash
  sudo apt-get install curl wget gnupg2 -y
  source /etc/os-release
  sudo sh -c "echo 'deb http://download.opensuse.org/repositories/devel:/kubic:/libcontainers:/stable/xUbuntu_${VERSION_ID}/ /' \
    > /etc/apt/sources.list.d/devel:kubic:libcontainers:stable.list"
  wget -nv https://download.opensuse.org/repositories/devel:kubic:libcontainers:stable/xUbuntu_${VERSION_ID}/Release.key -O- \
    | sudo apt-key add -
  sudo apt update
  ```

  Also, you need to install the `python-all` package, due to an `stdeb` bug that
  existed before v0.9.1:

  ```
  sudo apt-get install python-all -y
  ```
</details>

Add our repository following these instructions:

Download the GPG key for the repo:

```sh
gpg --keyserver hkps://keys.openpgp.org \
    --no-default-keyring --keyring ./fpf-apt-tools-archive-keyring.gpg \
    --recv-keys "DE28 AB24 1FA4 8260 FAC9 B8BA A7C9 B385 2260 4281"
sudo mkdir -p /etc/apt/keyrings/
sudo mv fpf-apt-tools-archive-keyring.gpg /etc/apt/keyrings
```

Add the URL of the repo in your APT sources:

```sh
source /etc/os-release
echo deb [signed-by=/etc/apt/keyrings/fpf-apt-tools-archive-keyring.gpg] \
    https://packages.freedom.press/apt-tools-prod ${VERSION_CODENAME?} main \
    | sudo tee /etc/apt/sources.list.d/fpf-apt-tools.list
```

Install Dangerzone:

```
sudo apt update
sudo apt install -y dangerzone
```

<details>
  <summary><i>:memo: Expand this section for a security notice on third-party Debian repos</i></summary>
  </br>

  This section follows the official instructions on configuring [third-party
  Debian repos](https://wiki.debian.org/DebianRepository/UseThirdParty).

  To mitigate a class of attacks against our APT repo (e.g., injecting packages
  signed with an attacker key), we add an additional step in our instructions to
  verify the downloaded GPG key against its fingerprint.

  Aside from these protections, the user needs to be aware that Debian packages
  run as `root` during the installation phase, so they need to place some trust
  on our signed Debian packages. This holds for any third-party Debian repo.
</details>

### Fedora

Type the following commands in a terminal:

```
sudo dnf config-manager --add-repo=https://packages.freedom.press/yum-tools-prod/dangerzone/dangerzone.repo
sudo dnf install dangerzone
```

<details>
<summary>Importing GPG key 0x22604281: ... Is this ok [y/N]:</summary>

After some minutes of running the above command (depending on your internet speed) you'll be asked to confirm the fingerprint of our signing key. This is to make sure that in the case our servers are compromized your computer stays safe. It should look like this:

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

> **Note**: If it does not show this fingerprint confirmation or the fingerprint does not match, it is possible that our servers were compromized. Be distrustful and reach out to us.

The `Fingerprint` should be `DE28 AB24 1FA4 8260 FAC9 B8BA A7C9 B385 2260 4281`. For extra security, you should confirm it matches the one at the bottom of our website ([dangerzone.rocks](https://dangerzone.rocks)) and our [Mastodon account](https://fosstodon.org/@dangerzone) bio.

After confirming that it matches, type `y` (for yes) and the installation should proceed.


</details>



## Build from source

If you'd like to build from source, follow the [build instructions](https://github.com/freedomofpress/dangerzone/blob/master/BUILD.md).
