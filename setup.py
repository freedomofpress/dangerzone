#!/usr/bin/env python3
import os
import sys

import setuptools

with open("share/version.txt") as f:
    version = f.read().strip()

qubes_target = os.environ.get("QUBES_TARGET") == "1"
if qubes_target:
    print("Target: Qubes OS")


def file_list(path):
    files = []
    for filename in os.listdir(path):
        if os.path.isfile(os.path.join(path, filename)):
            if qubes_target and filename.endswith("container.tar.gz"):
                continue  # ignore container when building a Qubes package
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
    ]
    if qubes_target:
        # Qubes RPC policy
        data_files.append(("/etc/qubes-rpc/", ["qubes/dz.Convert"]))
    return data_files


setuptools.setup(
    name="dangerzone",
    version=version,
    author="Freedom of the Press Foundation",
    author_email="info@freedom.press",
    license="MIT",
    description="Take potentially dangerous PDFs, office documents, or images and convert them to safe PDFs",
    long_description="""\
Dangerzone is an open source desktop application that takes potentially \
dangerous PDFs, office documents, or images and converts them to safe PDFs. \
It uses container technology to convert the documents within a secure sandbox.\
""",
    url="https://github.com/freedomofpress/dangerzone",
    packages=[
        "dangerzone",
        "dangerzone.conversion",
        "dangerzone.gui",
        "dangerzone.isolation_provider",
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
        ]
    },
)
