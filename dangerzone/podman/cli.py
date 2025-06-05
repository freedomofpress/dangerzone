#!/usr/bin/env python3

import sys

import click

from ..util import get_binary_path
from . import binary, errors


def main():
    try:
        cli()
    except errors.PodmanCommandError as e:
        click.secho(str(e), err=True, fg="red")
        if e.error.stderr:
            click.secho(f"Stderr: {e.error.stderr}", err=True, fg="red")
        # raise  # FIXME: Enable this in dev/verbose mode


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


@machine.command()
@click.option(
    "--image", help="Podman machine image", type=click.Path(exists=True, dir_okay=False)
)
@click.option("--cpus", help="Podman machine CPUs", type=int)
@click.option("--memory", "-m", help="Podman machine RAM (in MiB)", type=int)
@click.option("--disk-size", help="Podman machine disk sizse (in GiB)", type=int)
@click.option("--now", flag_value=True, help="Start the Podman machine now")
@click.argument("name", required=False)
@click.pass_obj
def init(podman, image, cpus, memory, disk_size, now, name):
    podman.machine.init(
        image=image, cpus=cpus, memory=memory, disk_size=disk_size, now=now, name=name
    )
