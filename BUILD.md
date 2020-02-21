# Development environment

After cloning this git repo, make sure to checkout the git submodules.

```
git submodule init
git submodule update
```

## Debian/Ubuntu

Install dependencies:

```sh
sudo apt install -y python-all python3-stdeb docker.io python3 python3-pyqt5 python3-appdirs python3-click python3-xdg
```

Run from source tree:

```sh
./dev_script/dangerzone
```

Create a .deb:

```sh
./install/linux/build_deb.py
```

## macOS

Install Xcode from the Mac App Store. Once it's installed, run it for the first time to set it up. Also, run this to make sure command line tools are installed: `xcode-select --install`. And finally, open Xcode, go to Preferences > Locations, and make sure under Command Line Tools you select an installed version from the dropdown. (This is required for installing Qt5.)

Download and install Python 3.7.4 from https://www.python.org/downloads/release/python-374/. I downloaded `python-3.7.4-macosx10.9.pkg`.

Install Qt 5.14.0 for macOS from https://www.qt.io/offline-installers. I downloaded `qt-opensource-mac-x64-5.14.0.dmg`. In the installer, you can skip making an account, and all you need is `Qt` > `Qt 5.14.0` > `macOS`.

If you don't have it already, install poetry (`pip3 install --user poetry`). Then install dependencies:

```sh
poetry install
```

Run from source tree:

```
poetry run ./dev_scripts/dangerzone
```

To create an app bundle and DMG for distribution, use the `build_app.py` script

```sh
poetry run ./install/macos/build_app.py
```

If you want to build for distribution, you'll need a codesigning certificate, and you'll also need to have [create-dmg](https://github.com/sindresorhus/create-dmg) installed:

```sh
npm install --global create-dmg
brew install graphicsmagick imagemagick
```

And then run `build_app.py --with-codesign`:

```sh
poetry run ./install/macos/build_app.py --with-codesign
```

The output is in the `dist` folder.

## Windows

These instructions include adding folders to the path in Windows. To do this, go to Start and type "advanced system settings", and open "View advanced system settings" in the Control Panel. Click Environment Variables. Under "System variables" double-click on Path. From there you can add and remove folders that are available in the PATH.

Download Python 3.7.6, 32-bit (x86) from https://www.python.org/downloads/release/python-376/. I downloaded python-3.7.6.exe. When installing it, make sure to check the "Add Python 3.7 to PATH" checkbox on the first page of the installer.

Install the Qt 5.14.1 from https://www.qt.io/offline-installers. I downloaded qt-opensource-windows-x86-5.14.1.exe. In the installer, unfortunately you have login to an account. Then all you need `Qt` > `Qt 5.14.1` > `MSVC 2017 32-bit`.

Install [poetry](https://python-poetry.org/). Open PowerShell, and run:

```
(Invoke-WebRequest -Uri https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py -UseBasicParsing).Content | python
```

And add `%USERPROFILE%\.poetry\bin` to your path. Then open a command prompt and cd to the `dangerzone` folder, and install the poetry dependencies:

```
poetry install
```

After that you can launch dangerzone during development with:

```
poetry run python dev_scripts\dangerzone
```

### If you want to build a .exe

Download and install the [Windows 10 SDK](https://developer.microsoft.com/en-US/windows/downloads/windows-10-sdk/).

Add the following directories to the path:

* `C:\Program Files (x86)\Windows Kits\10\bin\10.0.18362.0\x86`
* `C:\Program Files (x86)\Windows Kits\10\Redist\10.0.18362.0\ucrt\DLLs\x86`

### If you want the .exe to not get falsely flagged as malicious by anti-virus software

Dangerzone uses PyInstaller to turn the python source code into Windows executable `.exe` file. Apparently, malware developers also use PyInstaller, and some anti-virus vendors have included snippets of PyInstaller code in their virus definitions. To avoid this, you have to compile the Windows PyInstaller bootloader yourself instead of using the pre-compiled one that comes with PyInstaller.

Here's how to compile the PyInstaller bootloader:

Download and install [Microsoft Build Tools for Visual Studio 2017](https://www.visualstudio.com/downloads/#build-tools-for-visual-studio-2019). I downloaded `vs_buildtools__1378184674.1581551596.exe`. In the installer, check the box next to "C++ build tools". Click "Individual components", and under "Compilers, build tools and runtimes", check "Windows Universal CRT SDK". Then click install. When installation is done, you may have to reboot your computer.

Then, enable the 32-bit Visual C++ Toolset on the Command Line like this:

```
cd "C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Auxiliary\Build"
vcvars32.bat
```

Change to a folder where you keep source code, and clone the PyInstaller git repo and checkout the `v3.6` tag:

```
git clone https://github.com/pyinstaller/pyinstaller.git
cd pyinstaller
git tag -v v3.6
```

(Note that ideally you would verify the git tag, but the PGP key that has signed the v3.5 git tag for is not published anywhere, so this isn't possible. See [this issue](https://github.com/pyinstaller/pyinstaller/issues/4430).)

The next step is to compile the bootloader. We should do this all in dangerzone's poetry shell:

```
cd dangerzone
poetry shell
cd ..\pyinstaller
```

Then, compile the bootloader:

```
cd bootloader
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
* Add `C:\Program Files (x86)\WiX Toolset v3.1.1\bin` to the path.

### If you want to sign binaries with Authenticode

* You'll need a code signing certificate. I got an open source code signing certificate from [Certum](https://www.certum.eu/certum/cert,offer_en_open_source_cs.xml).
* Once you get a code signing key and certificate and covert it to a pfx file, import it into your certificate store.

## To make a .exe

Open a command prompt, cd into the dangerzone directory, and run:

```
poetry run pyinstaller install\pyinstaller\pyinstaller.spec
```

`dangerzone.exe` and all of their supporting files will get created inside the `dist` folder.

### To build the installer

Note that you must have a codesigning certificate installed in order to use the `install\windows\build.bat` script, because it codesigns `dangerzone.exe` and `Dangerzone.msi`.

Open a command prompt, cd to the dangerzone directory, and run:

```
poetry run install\windows\build.bat
```

When you're done you will have `dist\Dangerzone.msi`.