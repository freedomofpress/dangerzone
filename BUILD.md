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

Install Python 3.9.9 [[from python.org])(https://www.python.org/downloads/release/python-399/).

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

Install Python 3.9.9 (x86) [[from python.org])(https://www.python.org/downloads/release/python-399/). When installing it, make sure to check the "Add Python 3.9 to PATH" checkbox on the first page of the installer.

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

### If you want to build a .exe

Download and install the [Windows 10 SDK](https://developer.microsoft.com/en-US/windows/downloads/windows-10-sdk/).

Add the following directories to the path:

* `C:\Program Files (x86)\Windows Kits\10\bin\10.0.19041.0\x86`
* `C:\Program Files (x86)\Windows Kits\10\Redist\ucrt\DLLs\x86`

### If you want the .exe to not get falsely flagged as malicious by anti-virus software

Dangerzone uses PyInstaller to turn the python source code into Windows executable `.exe` file. Apparently, malware developers also use PyInstaller, and some anti-virus vendors have included snippets of PyInstaller code in their virus definitions. To avoid this, you have to compile the Windows PyInstaller bootloader yourself instead of using the pre-compiled one that comes with PyInstaller.

Here's how to compile the PyInstaller bootloader:

Download and install [Microsoft Build Tools for Visual Studio 2022](https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022). I downloaded `vs_BuildTools.exe`. In the installer, check the box next to "Desktop development with C++". Click "Individual components", and under "Compilers, build tools and runtimes", check "Windows Universal CRT SDK". Then click install. When installation is done, you may have to reboot your computer.

Then, enable the 32-bit Visual C++ Toolset on the Command Line like this:

```
cd 'C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build'
.\vcvars32.bat
```

Change to a folder where you keep source code, and clone the PyInstaller git repo and checkout the `v4.7` tag:

```
git clone https://github.com/pyinstaller/pyinstaller.git
cd pyinstaller
git checkout v4.7
```

The next step is to compile the bootloader. We should do this all in dangerzone's poetry shell:

```
cd dangerzone
poetry shell
cd ..\pyinstaller
```

Then, compile the bootloader:

```
cd .\bootloader\
python waf distclean all --target-arch=32bit --msvc_targets=x86
cd ..
```

Finally, install the PyInstaller module into your poetry environment:

```
python setup.py install
exit
```

Now the next time you use PyInstaller to build dangerzone, the `.exe` file should not be flagged as malicious by anti-virus.

### If you want to build the installer

* Go to https://dotnet.microsoft.com/download/dotnet-framework and download and install .NET Framework 3.5 SP1 Runtime. I downloaded `dotnetfx35.exe`.
* Go to https://wixtoolset.org/releases/ and download and install WiX toolset. I downloaded `wix311.exe`.
* Add `C:\Program Files (x86)\WiX Toolset v3.11\bin` to the path.

### If you want to sign binaries with Authenticode

You'll need a code signing certificate.

## To make a .exe

Open a command prompt, cd into the dangerzone directory, and run:

```
poetry run pyinstaller install\pyinstaller\pyinstaller.spec
```

`dangerzone.exe` and all of their supporting files will get created inside the `dist` folder.

You then must create a symbolic link for dangerzone to run. To do this, open a command prompt _as an administrator_, cd to the dangerzone folder, and run:

```
cd dist\dangerzone
mklink dangerzone-container.exe dangerzone.exe
```

### To build the installer

Note that you must have a codesigning certificate installed in order to use the `install\windows\build-app.bat` script, because it codesigns `dangerzone.exe` and `Dangerzone.msi`.

```
poetry run .\install\windows\build-app.bat
```

When you're done you will have `dist\Dangerzone.msi`.
