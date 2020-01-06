#!/usr/bin/env python3
import setuptools
import os
import sys
from dangerzone import dangerzone_version


setuptools.setup(
    name="dangerzone",
    version=dangerzone_version,
    author="Micah Lee",
    author_email="micah.lee@theintercept.com",
    license="MIT",
    description="Take arbitrary untrusted PDFs, office documents, or images and convert them to a trusted PDF",
    url="https://github.com/firstlookmedia/dangerzone",
    packages=["dangerzone"],
    classifiers=(
        "Development Status :: 4 - Beta",
        "Programming Language :: Python",
        "Intended Audience :: End Users/Desktop",
        "Operating System :: OS Independent",
    ),
    entry_points={"console_scripts": ["dangerzone = dangerzone:main"]},
)
