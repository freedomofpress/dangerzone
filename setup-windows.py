#!/usr/bin/env python3
import os
from cx_Freeze import setup, Executable

with open("share/version.txt") as f:
    version = f.read().strip()


setup(
    name="dangerzone",
    version=version,
    description="Take potentially dangerous PDFs, office documents, or images and convert them to a safe PDF",
    options={
        "build_exe": {
            "packages": ["dangerzone", "dangerzone.gui"],
            "excludes": ["test", "tkinter"],
            "include_files": [("share", "share"), ("LICENSE", "LICENSE")],
            "include_msvcr": True,
        }
    },
    executables=[
        Executable("install/windows/dangerzone.py", base="Win32GUI", icon="share/dangerzone.ico"),
        Executable("install/windows/dangerzone-cli.py", base=None, icon="share/dangerzone.ico"),
    ],
)
