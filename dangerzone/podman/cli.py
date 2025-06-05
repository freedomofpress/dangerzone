#!/usr/bin/env python3

import click

from ..util import get_binary_path
from . import binary


@click.group()
def cli():
    pass


@cli.command()
def list():
    path = get_binary_path("podman")
    podman = binary.PodmanBinary(path)
    ret = podman.machine.list()
    print(ret)
