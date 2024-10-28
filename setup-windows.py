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
            # Explicitly specify pymupdf.util module to fix building the executables
            # with cx_freeze. See https://github.com/marcelotduarte/cx_Freeze/issues/2653
            # for more details.
            # TODO: Upgrade to cx_freeze 7.3.0 which should include a fix.
            "packages": ["dangerzone", "dangerzone.gui", "pymupdf.utils"],
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
    ],
)
