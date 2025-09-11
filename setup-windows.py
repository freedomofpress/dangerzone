#!/usr/bin/env python3
from cx_Freeze import Executable, setup

with open("share/version.txt") as f:
    version = f.read().strip()


setup(
    name="dangerzone",
    version=version,
    # On Windows description will show as the app's name in the "Open With" menu. See:
    # https://github.com/freedomofpress/dangerzone/issues/283#issuecomment-1365148805
    description="Dangerzone",
    options={
        "build_exe": {
            "packages": ["dangerzone", "dangerzone.gui"],
            "excludes": ["test", "tkinter"],
            "include_files": [("share", "share"), ("LICENSE", "LICENSE")],
            "include_msvcr": True,
        }
    },
    executables=[
        Executable(
            "install/windows/dangerzone.py",
            base="Win32GUI",
            icon="share/dangerzone.ico",
        ),
        Executable(
            "install/windows/dangerzone-cli.py", base=None, icon="share/dangerzone.ico"
        ),
        Executable(
            "install/windows/dangerzone-image.py",
            base=None,
            icon="share/dangerzone.ico",
        ),
        Executable(
            "install/windows/dangerzone-machine.py",
            base=None,
            icon="share/dangerzone.ico",
        ),
    ],
)
