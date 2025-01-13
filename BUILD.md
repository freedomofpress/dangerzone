# Development environment

## Debian/Ubuntu

Install dependencies:

<table>
  <tr>
      <td>
<details>
  <summary><i>:memo: Expand this section if you are on Ubuntu 22.04 (Jammy).</i></summary>
  </br>

  The `conmon` version that Podman uses and Ubuntu Jammy ships, has a bug
  that gets triggered by Dangerzone
  (more details in https://github.com/freedomofpress/dangerzone/issues/685).
  If you want to run Dangerzone from source, you are advised to install a
  patched `conmon` version. A simple way to do so is to enable our
  apt-tools-prod repo, just for the `conmon` package:

  ```bash
  sudo cp ./dev_scripts/apt-tools-prod.sources /etc/apt/sources.list.d/
  sudo cp ./dev_scripts/apt-tools-prod.pref /etc/apt/preferences.d/
  ```

  The `conmon` package provided in the above repo was built with the
  following [instructions](https://github.com/freedomofpress/maint-dangerzone-conmon/tree/ubuntu/jammy/fpf).
  Alternatively, you can install a `conmon` version higher than `v2.0.25` from
  any repo you prefer.

</details>
    </td>
  </tr>
</table>


<table>
  <tr>
      <td>
<details>
  <summary><i>:memo: Expand this section if you are on Ubuntu 20.04 (Focal).</i></summary>
  </br>

  The default Python version that ships with Ubuntu Focal (3.8) is not
  compatible with PySide6, which requires Python 3.9 or greater.

  You can install Python 3.9 using the `python3.9` package.

  ```bash
  sudo apt install -y python3.9
  ```

  Poetry will automatically pick up the correct version when running.
</details>
    </td>
  </tr>
</table>


```sh
sudo apt install -y podman dh-python build-essential make libqt6gui6 \
    pipx python3 python3-dev
```

Install Poetry using `pipx` (recommended) and add it to your `$PATH`:

_(See also a list of [alternative installation
methods](https://python-poetry.org/docs/#installation))_

```sh
pipx ensurepath
pipx install poetry
pipx inject poetry poetry-plugin-export
```

After this, restart the terminal window, for the `poetry` command to be in your
`$PATH`.


Clone this repository:

```
git clone https://github.com/freedomofpress/dangerzone/
```

Change to the `dangerzone` folder, and install the poetry dependencies:

> **Note**: due to an issue with [poetry](https://github.com/python-poetry/poetry/issues/1917), if it prompts for your keyring, disable the keyring with `keyring --disable` and run the command again.

```
cd dangerzone
poetry install
```

Build the latest container:

```sh
python3 ./install/common/build-image.py
```

Download the OCR language data:

```sh
python3 ./install/common/download-tessdata.py
```

Run from source tree:

```sh
# start a shell in the virtual environment
poetry shell

# run the CLI
./dev_scripts/dangerzone-cli --help

# run the GUI
./dev_scripts/dangerzone
```

Create a .deb:

```sh
./install/linux/build-deb.py
```

## Fedora

Install dependencies:

```sh
sudo dnf install -y rpm-build podman python3 python3-devel python3-poetry-core \
    pipx qt6-qtbase-gui
```

<table>
  <tr>
      <td>
<details>
  <summary><i>:memo: Expand this section if you are on Fedora 41.</i></summary>
  </br>

  The default Python version that ships with Fedora 41 (3.13) is not
  compatible with PySide6, which requires Python 3.12 or earlier.

  You can install Python 3.12 using the `python3.12` package.

  ```bash
  sudo dnf install -y python3.12
  ```

  Poetry will automatically pick up the correct version when running.
</details>
    </td>
  </tr>
</table>

Install Poetry using `pipx`:

```sh
pipx install poetry
pipx inject poetry poetry-plugin-export
```

Clone this repository:

```
git clone https://github.com/freedomofpress/dangerzone/
```

Change to the `dangerzone` folder, and install the poetry dependencies:

> **Note**: due to an issue with [poetry](https://github.com/python-poetry/poetry/issues/1917), if it prompts for your keyring, disable the keyring with `keyring --disable` and run the command again.

```
cd dangerzone
poetry install
```

Build the latest container:

```sh
python3 ./install/common/build-image.py
```

Download the OCR language data:

```sh
python3 ./install/common/download-tessdata.py
```

Run from source tree:

```sh
# start a shell in the virtual environment
poetry shell

# run the CLI
./dev_scripts/dangerzone-cli --help

# run the GUI
./dev_scripts/dangerzone
```

> [!NOTE]
> Prefer running the following command in a Fedora development environment,
> created by `./dev_script/env.py`.

Create a .rpm:

```sh
./install/linux/build-rpm.py
```

## Qubes OS


> :warning: Native Qubes support is in beta stage, so the instructions below
> require switching between qubes, and are subject to change.
>
> If you want to build Dangerzone on Qubes and use containers instead of disposable
> qubes, please follow the instructions of Fedora / Debian instead.


### Initial Setup

The following steps must be completed once. Make sure you run them in the
specified qubes.

Overview of the qubes you'll create:

| qube         |   type   | purpose |
|--------------|----------|---------|
| dz           | app qube | Dangerzone development |
| dz-dvm       | app qube | offline disposable template for performing conversions |
| fedora-40-dz | template | template for the other two qubes |

#### In `dom0`:

The following instructions require typing commands in a terminal in dom0.

1. Create a new Fedora **template** (`fedora-40-dz`) for Dangerzone development:

   ```
   qvm-clone fedora-40 fedora-40-dz
   ```

   > :bulb: Alternatively, you can use your base Fedora 40 template in the
   > following instructions. In that case, skip this step and replace
   > `fedora-40-dz` with `fedora-40` in the steps below.

2. Create an offline disposable template (app qube) called `dz-dvm`, based on the `fedora-40-dz`
   template. This will be the qube where the documents will be sanitized:

   ```
   qvm-create --class AppVM --label red --template fedora-40-dz \
       --prop netvm="" --prop template_for_dispvms=True \
       --prop default_dispvm='' dz-dvm
   ```

3. Create an **app** qube (`dz`) that will be used for Dangerzone development
   and initiating the sanitization process:

   ```
   qvm-create --class AppVM --label red --template fedora-40-dz dz
   qvm-volume resize dz:private $(numfmt --from=auto 20Gi)
   ```

   > :bulb: Alternatively, you can use a different app qube for Dangerzone
   > development. In that case, replace `dz` with the qube of your choice in the
   > steps below.
   >
   > In the commands above, we also resize the private volume of the `dz` qube
   > to 20GiB, since you may need some extra storage space when developing on
   > Dangerzone (e.g., for container images, Tesseract data, and Python
   > virtualenvs).

4. Add an RPC policy (`/etc/qubes/policy.d/50-dangerzone.policy`) that will
   allow launching a disposable qube (`dz-dvm`) when Dangerzone converts a
   document, with the following contents:

   ```
   dz.Convert         *       @anyvm       @dispvm:dz-dvm  allow
   dz.ConvertDev      *       @anyvm       @dispvm:dz-dvm  allow
   ```

#### In the `dz` app qube

In the following steps you'll setup the development environment and
install a dangerzone build. This will make the development faster since it
loads the server code dynamically each time it's run, instead of having
to build and install a server package each time the developer wants to
test it.

1. Clone the Dangerzone project:

   ```
   git clone https://github.com/freedomofpress/dangerzone
   cd dangerzone
   ```

2. Follow the Fedora instructions for setting up the development environment.

3. Build a dangerzone `.rpm` for qubes with the command

   ```sh
   ./install/linux/build-rpm.py --qubes
   ```

4. Copy the produced `.rpm` file into `fedora-40-dz`
   ```sh
   qvm-copy dist/*.x86_64.rpm
   ```

#### In the `fedora-40-dz` template

1. Install the `.rpm` package you just copied

   ```sh
   sudo dnf install ~/QubesIncoming/dz/*.rpm
   ```

2. Shutdown the `fedora-40-dz` template

### Developing Dangerzone

From here on, developing Dangerzone is similar to Fedora. The only differences
are that you need to set the environment variable `QUBES_CONVERSION=1` when
you wish to test the Qubes conversion, run the following commands on the `dz` development qube:

```sh

# run the CLI
QUBES_CONVERSION=1 poetry run ./dev_scripts/dangerzone-cli --help

# run the GUI
QUBES_CONVERSION=1 poetry run ./dev_scripts/dangerzone
```

And when creating a `.rpm` you'll need to enable the `--qubes` flag.

> [!NOTE]
> Prefer running the following command in a Fedora development environment,
> created by `./dev_script/env.py`.

```sh
./install/linux/build-rpm.py --qubes
```

For changes in the server side components, you can simply edit them locally,
and they will be mirrored to the disposable qube through the `dz.ConvertDev`
RPC call.

The only reason to build a new Qubes RPM and install it in the `fedora-40-dz`
template for development is if:
1. The project requires new server-side components.
2. The code for `qubes/dz.ConvertDev` needs to be updated.

## macOS

Install [Docker Desktop](https://www.docker.com/products/docker-desktop). Make sure to choose your correct CPU, either Intel Chip or Apple Chip.

Install the latest version of Python 3.12 [from python.org](https://www.python.org/downloads/macos/), and make sure `/Library/Frameworks/Python.framework/Versions/3.12/bin` is in your `PATH`.

Clone this repository:

```
git clone https://github.com/freedomofpress/dangerzone/
cd dangerzone
```

Install Python dependencies:

```sh
python3 -m pip install poetry poetry-plugin-export
poetry install
```

Install [Homebrew](https://brew.sh/) dependencies:

```sh
brew install create-dmg
```

Build the dangerzone container image:

```sh
python3 ./install/common/build-image.py
```

Download the OCR language data:

```sh
python3 ./install/common/download-tessdata.py
```

Run from source tree:

```sh
# start a shell in the virtual environment
poetry shell

# run the CLI
./dev_scripts/dangerzone-cli --help

# run the GUI
./dev_scripts/dangerzone
```

To create an app bundle, use the `build_app.py` script:

```sh
poetry run ./install/macos/build-app.py
```

If you want to build for distribution, you'll need a codesigning certificate, and then run:

```sh
poetry run ./install/macos/build-app.py --with-codesign
```

The output is in the `dist` folder.

## Windows

Install [Docker Desktop](https://www.docker.com/products/docker-desktop).

Install the latest version of Python 3.12 (64-bit) [from python.org](https://www.python.org/downloads/windows/). Make sure to check the "Add Python 3.12 to PATH" checkbox on the first page of the installer.


Install Microsoft Visual C++ 14.0 or greater. Get it with ["Microsoft C++ Build Tools"](https://visualstudio.microsoft.com/visual-cpp-build-tools/) and make sure to select "Desktop development with C++" when installing.

Install [poetry](https://python-poetry.org/). Open PowerShell, and run:

```
python -m pip install poetry poetry-plugin-export
```

Install git from [here](https://git-scm.com/download/win), open a Windows terminal (`cmd.exe`) and clone this repository:

```
git clone https://github.com/freedomofpress/dangerzone/
```

Change to the `dangerzone` folder, and install the poetry dependencies:

```
cd dangerzone
poetry install
```

Build the dangerzone container image:

```sh
python3 .\install\common\build-image.py
```

Download the OCR language data:

```sh
python3 .\install\common\download-tessdata.py
```

After that you can launch dangerzone during development with:

```
# start a shell in the virtual environment
poetry shell

# run the CLI
.\dev_scripts\dangerzone-cli.bat --help

# run the GUI
.\dev_scripts\dangerzone.bat
```

### If you want to build the Windows installer

Install [.NET SDK](https://dotnet.microsoft.com/en-us/download) version 6 or later. Then, open a terminal and install the latest version of [WiX Toolset .NET tool](https://wixtoolset.org/) **v5** with:

```sh
dotnet tool install --global wix --version 5.*
```

Install the WiX UI extension. You may need to open a new terminal in order to use the newly installed `wix` .NET tool:

```sh
wix extension add --global WixToolset.UI.wixext/5.x.y
```

> [!IMPORTANT]
> To avoid compatibility issues, ensure the WiX UI extension version matches the version of the WiX Toolset.
>
> Run `wix --version` to check the version of WiX Toolset you have installed and replace `5.x.y` with the full version number without the Git revision.

### If you want to sign binaries with Authenticode

You'll need a code signing certificate.

## To make a .exe

Open a command prompt, cd into the dangerzone directory, and run:

```
poetry run python .\setup-windows.py build
```

In `build\exe.win32-3.12\` you will find `dangerzone.exe`, `dangerzone-cli.exe`, and all supporting files.

### To build the installer

Note that you must have a codesigning certificate installed in order to use the `install\windows\build-app.bat` script, because it codesigns `dangerzone.exe`, `dangerzone-cli.exe` and `Dangerzone.msi`.

```
poetry run .\install\windows\build-app.bat
```

When you're done you will have `dist\Dangerzone.msi`.

## Updating the container image

The Dangezone container image is reproducible. This means that every time we
build it, the result will be bit-for-bit the same, with some minor exceptions.
Read more on how you can update it in `docs/developer/reproducibility.md`.
