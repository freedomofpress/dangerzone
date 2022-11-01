Dangerzone 0.3 is available for:

- Ubuntu 22.04 (jammy)
- Debian 11 (bullseye)
- Fedora 36
- Fedora 35

### Ubuntu, Debian

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
