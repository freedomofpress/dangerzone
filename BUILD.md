# Development environment

After cloning this git repo, make sure to checkout the git submodules.

```
git submodule init
git submodule update
```

## Debian/Ubuntu

You need [podman](https://podman.io/getting-started/installation) ([these instructions](https://kushaldas.in/posts/podman-on-debian-buster.html) are useful for installing in Debian or Ubuntu).

Install dependencies:

```sh
sudo apt install -y python3 python3-pyqt5 python3-appdirs python3-click python3-xdg
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

If you don't have it already, install pipenv (`pip3 install --user pipenv`). Then install dependencies:

```sh
pipenv install --dev --pre
```

Run from source tree:

```
pipenv run ./dev_scripts/dangerzone
```

To create an app bundle and DMG for distribution, use the `build_app.py` script

```sh
pipenv run ./install/macos/build_app.py
```

If you want to build for distribution, you'll need a codesigning certificate, and you'll also need to have [create-dmg](https://github.com/sindresorhus/create-dmg) installed:

```sh
npm install --global create-dmg
brew install graphicsmagick imagemagick
```

And then run `build_app.py --with-codesign`:

```sh
pipenv run ./install/macos/build_app.py --with-codesign
```

The output is in the `dist` folder.

## Windows

Download Python 3.7.6, 32-bit (x86) from https://www.python.org/downloads/release/python-376/. I downloaded python-3.7.6.exe. When installing it, make sure to check the "Add Python 3.7 to PATH" checkbox on the first page of the installer.

Open a command prompt and cd to the gpgsync folder. If you don't have it already, install pipenv (`pip install pipenv`). Then install dependencies:

```
python -m pipenv install --dev
```

Install the Qt 5.14.1 from https://www.qt.io/offline-installers. I downloaded qt-opensource-windows-x86-5.14.1.exe. In the installer, unfortunately you have login to an account. Then all you need `Qt` > `Qt 5.14.1` > `MSVC 2017 32-bit`.

After that you can launch GPG Sync during development with:

```
python -m pipenv run python dev_scripts\dangerzone
```
