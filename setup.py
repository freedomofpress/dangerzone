#!/usr/bin/env python3
import os
import sys

import setuptools

with open("share/version.txt") as f:
    version = f.read().strip()


def file_list(path):
    files = []
    for filename in os.listdir(path):
        if os.path.isfile(os.path.join(path, filename)):
            files.append(os.path.join(path, filename))
    return files


setuptools.setup(
    name="dangerzone",
    version=version,
    author="Micah Lee",
    author_email="micah.lee@theintercept.com",
    license="MIT",
    description="Take potentially dangerous PDFs, office documents, or images and convert them to safe PDFs",
    long_description="""\
Dangerzone is an open source desktop application that takes potentially \
dangerous PDFs, office documents, or images and converts them to safe PDFs. \
It uses container technology to convert the documents within a secure sandbox.\
""",
    url="https://github.com/freedomofpress/dangerzone",
    packages=["dangerzone", "dangerzone.gui", "dangerzone.isolation_provider"],
    data_files=[
        (
            "share/applications",
            ["install/linux/media.firstlook.dangerzone.desktop"],
        ),
        (
            "share/icons/hicolor/64x64/apps",
            ["install/linux/media.firstlook.dangerzone.png"],
        ),
        ("share/dangerzone", file_list("share")),
    ],
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
