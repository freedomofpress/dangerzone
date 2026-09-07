# Operating System support

Dangerzone can run on various Operating Systems (OS), and has automated tests
for most of them.
This section explains which OS we support, how long we support each version, and
how do we test Dangerzone against these.

You can find general support information in this table, and more details in the
following sections.

(Unless specified, the architecture of the OS is AMD64)

| Distribution             | Supported releases        | Automated tests                      | Manual QA |
| ------------------------ | ------------------------- | ------------------------------------ | --------- |
| [Windows](../how-to/install.md#windows)      | 2 last releases ⥿         | 🗹 (`windows-2022`, `windows-2025`) ◎ | 🗹         |
| [macOS intel](../how-to/install.md#macos)    | 3 last releases           | 🗹 (`macos-15`) ◎                     | 🗹         |
| [macOS silicon](../how-to/install.md#macos)  | 3 last releases           | 🗹 (`macos-15`) ◎                     | 🗹         |
| [Ubuntu](../how-to/install.md#ubuntu-debian) | Follow upstream support   | 🗹                                    | 🗹         |
| [Debian](../how-to/install.md#ubuntu-debian) | Current stable, Oldstable and LTS releases | 🗹                   | 🗹         |
| [Fedora](../how-to/install.md#fedora)        | Follow upstream support   | 🗹                                    | 🗹         |
| [Qubes OS](../how-to/install.md#qubes-os)    | [Beta support](https://github.com/freedomofpress/dangerzone/issues/413) ✢ | 🗷 | Latest Fedora template |
| [Tails](../how-to/install.md#tails)          | Only the last release     | 🗷              | Last release only |

Notes:

⥿ We provide support for Windows 10 on a best effort basis, given that it is currently end of life.
  Windows on Arm [is not supported at this time](https://github.com/freedomofpress/dangerzone/issues/1228).

✢ Qubes OS support assumes the use of a Fedora template. The supported releases follow our general support for Fedora.

◎ More information [in the runner-images repository](https://github.com/actions/runner-images/tree/main)

## Note on unsupported Linux distros

`.deb` and `.rpm` packages are provided for supported distributions. Users of **other** Debian-based or Fedora-based distros — that are not listed above — may be able to install Dangerzone through these packages. Unfortunately, Dangerzone is not tested against these distros, and might fail to install, update, run, or be broken in subtle ways.

Please, proceed at your own risks, only if you know what you're doing.
