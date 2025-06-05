#!/usr/bin/env python3

import sys

import click

from ..util import get_binary_path
from . import binary


@click.group()
@click.pass_context
def cli(ctx):
    path = get_binary_path("podman")
    podman = binary.PodmanBinary(path)
    ctx.obj = podman


@cli.command(
    context_settings=dict(
        allow_extra_args=True,
        ignore_unknown_options=True,
    )
)
@click.pass_obj
def raw(podman):
    podman.runner.run_raw(sys.argv[2:], capture_output=False)


@cli.group()
@click.pass_context
def machine(ctx):
    pass


@machine.command()
@click.pass_obj
def list(podman):
    ret = podman.machine.list()
    print(ret)
