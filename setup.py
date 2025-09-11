#!/usr/bin/env python3
import os

import setuptools

with open("share/version.txt") as f:
    version = f.read().strip()


def file_list(path):
    files = []
    for filename in os.listdir(path):
        if os.path.isfile(os.path.join(path, filename)):
            files.append(os.path.join(path, filename))
    return files


def data_files_list():
    data_files = [
        (
            "share/applications",
            ["install/linux/press.freedom.dangerzone.desktop"],
        ),
        (
            "share/icons/hicolor/64x64/apps",
            ["install/linux/press.freedom.dangerzone.png"],
        ),
        ("share/dangerzone", file_list("share")),
        ("share/dangerzone/vendor", file_list("share/vendor")),
    ]
    return data_files


setuptools.setup(
    name="dangerzone",
    version=version,
    author="Freedom of the Press Foundation",
    author_email="info@freedom.press",
    license="AGPL-3.0",
    description="Take potentially dangerous PDFs, office documents, or images and convert them to safe PDFs",
    long_description="""\
Dangerzone is an open source desktop application that takes potentially \
dangerous PDFs, office documents, or images and converts them to safe PDFs. \
It uses disposable VMs on Qubes OS, or container technology in other OSes, to \
convert the documents within a secure sandbox.
""",
    url="https://github.com/freedomofpress/dangerzone",
    packages=[
        "dangerzone",
        "dangerzone.conversion",
        "dangerzone.gui",
        "dangerzone.isolation_provider",
        "dangerzone.podman",
        "dangerzone.podman.command",
        "dangerzone.podman.errors",
        "dangerzone.updater",
    ],
    data_files=data_files_list(),
    classifiers=[
        "Programming Language :: Python",
        "Intended Audience :: End Users/Desktop",
        "Operating System :: OS Independent",
    ],
    entry_points={
        "console_scripts": [
            "dangerzone = dangerzone:main",
            "dangerzone-cli = dangerzone:main",
            "dangerzone-image = dangerzone.updater.cli:main",
            "dangerzone-machine= dangerzone.podman.cli:main",
        ]
    },
)
