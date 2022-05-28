# Development environment

## Debian/Ubuntu

Install dependencies:

```sh
sudo apt install -y podman dh-python python3 python3-stdeb python3-pyside2.qtcore python3-pyside2.qtgui python3-pyside2.qtwidgets python3-appdirs python3-click python3-xdg python3-requests python3-colorama python3-psutil
```

Build the latest container:

```sh
./install/linux/build-image.sh
```

Run from source tree:

```sh
./dev_scripts/dangerzone
```

Create a .deb:

```sh
./install/linux/build-deb.py
```

## Fedora

Install dependencies:

```sh
sudo dnf install -y rpm-build podman python3 python3-setuptools python3-pyside2 python3-appdirs python3-click python3-pyxdg python3-requests python3-colorama python3-psutil
```

Build the latest container:

```sh
./install/linux/build-image.sh
```

Run from source tree:

```sh
./dev_scripts/dangerzone
```

Create a .rpm:

```sh
./install/linux/build-rpm.py
```

## macOS

Install Xcode from the App Store.

Install [Docker Desktop](https://www.docker.com/products/docker-desktop). Make sure to choose your correct CPU, either Intel Chip or Apple Chip.

Install Python 3.10.4 [from python.org](https://www.python.org/downloads/release/python-3104/).

Install Python dependencies:

```sh
pip3 install --user poetry
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

Install Python 3.10.4 (x86) [from python.org](https://www.python.org/downloads/release/python-3104/). When installing it, make sure to check the "Add Python 3.10 to PATH" checkbox on the first page of the installer.

Install [poetry](https://python-poetry.org/). Open PowerShell, and run:

```
(Invoke-WebRequest -Uri https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py -UseBasicParsing).Content | python
```

Change to the `dangerzone` folder, and install the poetry dependencies:

```
poetry install
```

Build the dangerzone container image:

```sh
python .\install\windows\build-image.py
```

After that you can launch dangerzone during development with:

```
.\dev_scripts\dangerzone.bat
.\dev_scripts\dangerzone-cli.bat --help
```

### If you want to build the installer

* Go to https://dotnet.microsoft.com/download/dotnet-framework and download and install .NET Framework 3.5 SP1 Runtime. I downloaded `dotnetfx35.exe`.
* Go to https://wixtoolset.org/releases/ and download and install WiX toolset. I downloaded `wix311.exe`.
* Add `C:\Program Files (x86)\WiX Toolset v3.11\bin` to the path.

### If you want to sign binaries with Authenticode

You'll need a code signing certificate.

## To make a .exe

Open a command prompt, cd into the dangerzone directory, and run:

```
poetry run python .\setup-windows.py build
```

In `build\exe.win32-3.10\` you will find `dangerzone.exe`, `dangerzone-cli.exe`, and all supporting files.

### To build the installer

Note that you must have a codesigning certificate installed in order to use the `install\windows\build-app.bat` script, because it codesigns `dangerzone.exe`, `dangerzone-cli.exe` and `Dangerzone.msi`.

```
poetry run .\install\windows\build-app.bat
```

When you're done you will have `dist\Dangerzone.msi`.
