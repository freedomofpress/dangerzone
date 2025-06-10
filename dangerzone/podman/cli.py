#!/usr/bin/env python3

import sys
import tempfile

import click

from ..util import get_binary_path, get_resource_path
from . import binary, errors

CONTAINERS_CONF = """\
[engine]
helper_binaries_dir={helper_binaries_dir}

[machine]
cpus={cpus}
volumes=[]
"""


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
    # FIXME: Delete the temporary file on closure
    with tempfile.NamedTemporaryFile(mode="w+", delete=False) as f:
        cpus = 4
        helper_binaries_dir = [str(get_resource_path("vendor") / "podman")]
        conf = CONTAINERS_CONF.format(
            cpus=cpus, helper_binaries_dir=helper_binaries_dir
        )
        f.write(conf)
        f.flush()

    path = get_binary_path("podman")
    podman = binary.PodmanBinary(path, containers_conf=f.name)
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
# FIXME: Change this name to something more unique
@click.argument("name", default="dz")
@click.pass_obj
def init(podman, image, cpus, memory, disk_size, now, name):
    podman.machine.init(
        image=image, cpus=cpus, memory=memory, disk_size=disk_size, now=now, name=name
    )


@machine.command()
# FIXME: Change this name to something more unique
@click.argument("name", default="dz")
@click.pass_obj
def start(podman, name):
    podman.machine.start(name=name)


@machine.command()
# FIXME: Change this name to something more unique
@click.argument("name", default="dz")
@click.pass_obj
def stop(podman, name):
    podman.machine.stop(name=name)


@machine.command()
# FIXME: Change this name to something more unique
@click.argument("name", default="dz")
@click.option(
    "--force", "-f", flag_value=True, help="Stop and delete without confirmation"
)
@click.option("--save_image", flag_value=True, help="Do not delete the VM image")
@click.pass_obj
def remove(podman, force, save_image, name):
    podman.machine.remove(name=name, force=force, save_image=save_image)


@machine.command()
@click.option(
    "--force", "-f", flag_value=True, help="Stop and delete without confirmation"
)
@click.pass_obj
def reset(podman, force):
    podman.machine.reset(force=force)
