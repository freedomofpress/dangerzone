# Development environment

## Debian/Ubuntu

Install dependencies:

```sh
sudo apt install -y podman dh-python build-essential fakeroot make libqt6gui6 \
    pipx python3 python3-dev python3-stdeb python3-all
```

Install Poetry using `pipx` (recommended) and add it to your `$PATH`:

_(See also a list of [alternative installation
methods](https://python-poetry.org/docs/#installation))_

```sh
pipx ensurepath
pipx install poetry
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
./install/linux/build-image.sh
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

Install Poetry using `pipx`:

```sh
pipx install poetry
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
./install/linux/build-image.sh
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
> qubes, please follow the intructions of Fedora / Debian instead.


### Initial Setup

The following steps must be completed once. Make sure you run them in the
specified qubes.

Overview of the qubes you'll create:

| qube         |   type   | purpose |
|--------------|----------|---------|
| dz           | app qube | Dangerzone development |
| dz-dvm       | app qube | offline diposable template for performing conversions |
| fedora-38-dz | template | template for the other two qubes |

#### In `dom0`:

The following instructions require typing commands in a terminal in dom0.

1. Create a new Fedora **template** (`fedora-38-dz`) for Dangerzone development:

   ```
   qvm-clone fedora-38 fedora-38-dz
   ```

   > :bulb: Alternatively, you can use your base Fedora 38 template in the
   > following instructions. In that case, skip this step and replace
   > `fedora-38-dz` with `fedora-38` in the steps below.

2. Create an offline disposable template (app qube) called `dz-dvm`, based on the `fedora-38-dz`
   template. This will be the qube where the documents will be sanitized:

   ```
   qvm-create --class AppVM --label red --template fedora-38-dz \
       --prop netvm=""  --prop template_for_dispvms=True \
       --prop default_dispvm='' dz-dvm
   ```

3. Create an **app** qube (`dz`) that will be used for Dangerzone development
   and initiating the sanitization process:

   ```
   qvm-create --class AppVM --label red --template fedora-38-dz dz
   ```

   > :bulb: Alternatively, you can use a different app qube for Dangerzone
   > development. In that case, replace `dz` with the qube of your choice in the
   > steps below.

4. Add an RPC policy (`/etc/qubes/policy.d/50-dangerzone.policy`) that will
   allow launching a disposable qube (`dz-dvm`) when Dangerzone converts a
   document, with the following contents:

   ```
   dz.Convert         *       @anyvm       @dispvm:dz-dvm  allow
   dz.ConvertDev      *       @anyvm       @dispvm:dz-dvm  allow
   ```

#### In the `fedora-38-dz` template

1. Install dependencies:

   ```
   sudo dnf install -y rpm-build podman python3 python3-devel \
       python3-poetry-core pipx qt6-qtbase-gui libreoffice python3-magic \
       python3-keyring tesseract*
   ```

2. Shutdown the `fedora-38-dz` template:

   ```
   shutdown -h now
   ```

#### In the `dz` app qube

1. Clone the Dangerzone project:

   ```
   git clone https://github.com/freedomofpress/dangerzone
   cd dangerzone
   ```

2. Install Poetry using `pipx`:

   ```sh
   pipx install poetry
   ```

3. Install the poetry dependencies:

   ```
   poetry install
   ```

   > **Note**: due to an issue with
   > [poetry](https://github.com/python-poetry/poetry/issues/1917), if it
   > prompts for your keyring, disable the keyring with `keyring --disable` and
   > run the command again.

4. Change to the `dangerzone` folder and copy the Qubes RPC calls into the
   template for the **disposable** qube that will be used for document
   sanitization (`dz-dvm`):

   ```
   qvm-copy qubes/*
   ```

   And then choose `dz-dvm` as the target.

#### In the `dz-dvm` template

1. Create the directory that will contain the Dangerzone RPC calls, if it does
   not exist already:

   ```
   sudo mkdir -p /rw/usrlocal/etc/qubes-rpc/
   ```

2. Move the files we copied in the previous step to their proper place:

   ```
   sudo cp ~/QubesIncoming/dz/* /rw/usrlocal/etc/qubes-rpc/
   ```

3. Shutdown the `dz-dvm` qube:

   ```
   shutdown -h now
   ```

### Developing Dangerzone

From here on, developing Dangerzone is similar as in other Linux platforms. You
can run the following commands in the `dz` app qube:

```sh
# start a shell in the virtual environment
poetry shell

# run the CLI
QUBES_CONVERSION=1 ./dev_scripts/dangerzone-cli --help

# run the GUI
QUBES_CONVERSION=1 ./dev_scripts/dangerzone
```

Create a .rpm:

> [!NOTE]
> Prefer running the following command in a Fedora development environment,
> created by `./dev_script/env.py`.

```sh
./install/linux/build-rpm.py --qubes
```

For changes in the server side components, you can simply edit them locally,
and they will be mirrored to the disposable qube through the `dz.ConvertDev`
RPC call.

The only reason to update the `fedora-38-dz` template from there on is if:
1. The project requires new server-side components.
2. The code for `dz.ConvertDev` needs to be updated. Copy the updated file
   as we've shown in the steps above.

### Installing Dangerzone system-wide

If you want to test the .rpm you just created, you can do the following:

On the `dz` app cube, copy the built `dangerzone.rpm` to `fedora-38-dz`
template:

```
qvm-copy-to-vm fedora-38-dz dist/dangerzone*.noarch.rpm
```

On the `fedora-38-dz` template, install the copied .rpm:

```
sudo dnf install -y ~/QubesIncoming/dz/dangerzone-*.rpm
```

Shutdown the `fedora-38-dz` template and the `dz` app qube, and then you can
refresh the applications on the `dz` qube, find Dangerzone in the list, and use
it to convert a document.

## macOS

Install [Docker Desktop](https://www.docker.com/products/docker-desktop). Make sure to choose your correct CPU, either Intel Chip or Apple Chip.

Install the latest version of Python 3.11 [from python.org](https://www.python.org/downloads/macos/), and make sure `/Library/Frameworks/Python.framework/Versions/3.11/bin` is in your `PATH`.

Clone this repository:

```
git clone https://github.com/freedomofpress/dangerzone/
cd dangerzone
```

Install Python dependencies:

```sh
python3 -m pip install poetry
poetry install
```

Install [Homebrew](https://brew.sh/) dependencies:

```sh
brew install create-dmg
```

Build the dangerzone container image:

```sh
./install/macos/build-image.sh
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

Install the latest version of Python 3.11 (64-bit) [from python.org](https://www.python.org/downloads/windows/). Make sure to check the "Add Python 3.11 to PATH" checkbox on the first page of the installer.


Install Microsoft Visual C++ 14.0 or greater. Get it with ["Microsoft C++ Build Tools"](https://visualstudio.microsoft.com/visual-cpp-build-tools/) and make sure to select "Desktop development with C++" when installing.

Install [poetry](https://python-poetry.org/). Open PowerShell, and run:

```
python -m pip install poetry
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
python .\install\windows\build-image.py
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

### If you want to build the installer

* Go to https://dotnet.microsoft.com/download/dotnet-framework and download and install .NET Framework 3.5 SP1 Runtime. I downloaded `dotnetfx35.exe`.
* Go to https://wixtoolset.org/releases/ and download and install WiX toolset. I downloaded `wix311.exe`.
* Add `C:\Program Files (x86)\WiX Toolset v3.11\bin` to the path ([instructions](https://web.archive.org/web/20230221104142/https://windowsloop.com/how-to-add-to-windows-path/)).

### If you want to sign binaries with Authenticode

You'll need a code signing certificate.

## To make a .exe

Open a command prompt, cd into the dangerzone directory, and run:

```
poetry run python .\setup-windows.py build
```

In `build\exe.win32-3.11\` you will find `dangerzone.exe`, `dangerzone-cli.exe`, and all supporting files.

### To build the installer

Note that you must have a codesigning certificate installed in order to use the `install\windows\build-app.bat` script, because it codesigns `dangerzone.exe`, `dangerzone-cli.exe` and `Dangerzone.msi`.

```
poetry run .\install\windows\build-app.bat
```

When you're done you will have `dist\Dangerzone.msi`.
