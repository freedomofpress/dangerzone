#!/usr/bin/env python3
import setuptools
import os
import sys

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
    description="Take potentially dangerous PDFs, office documents, or images and convert them to a safe PDF",
    url="https://github.com/firstlookmedia/dangerzone",
    packages=["dangerzone"],
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
        (
            "share/polkit-1/actions",
            ["install/linux/media.firstlook.dangerzone-container.policy"],
        ),
    ],
    classifiers=[
        "Programming Language :: Python",
        "Intended Audience :: End Users/Desktop",
        "Operating System :: OS Independent",
    ],
    entry_points={
        "console_scripts": [
            "dangerzone = dangerzone:main",
            "dangerzone-container = dangerzone:container_main",
        ]
    },
)
