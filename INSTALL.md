Dangerzone is available for:

- Ubuntu 22.04 (jammy)
- Ubuntu 20.04 (focal)
- Debian 12 (bookworm)
- Debian 11 (bullseye)
- Fedora 37
- Fedora 36
- Fedora 35

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
</details>

Add our repository following [these instructions](https://packagecloud.io/firstlookmedia/code/install#manual-deb), or by running this script:

```
curl -s https://packagecloud.io/install/repositories/firstlookmedia/code/script.deb.sh | sudo bash
```

Install Dangerzone:

```
sudo apt update
sudo apt install -y dangerzone
```

### Fedora

Add our repository following [these instructions](https://packagecloud.io/firstlookmedia/code/install#manual-rpm), or by running this script:

```
curl -s https://packagecloud.io/install/repositories/firstlookmedia/code/script.rpm.sh | sudo bash
```

Install Dangerzone:

```
sudo dnf install -y dangerzone
```

## Build from source

If you'd like to build from source, follow the [build instructions](https://github.com/firstlookmedia/dangerzone/blob/master/BUILD.md).
