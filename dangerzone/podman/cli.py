#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os
import sys

import click

from .errors import PodmanError
from .machine import PodmanMachineManager

logger = logging.getLogger(__name__)


@click.group()
@click.option(
    "--log-level",
    default="info",
    type=click.Choice(["debug", "info", "warning", "error", "critical"]),
    help="Set the logging level.",
)
def main(log_level):
    """Manage Dangerzone Podman machines."""
    logging.basicConfig(level=getattr(logging, log_level.upper()), stream=sys.stderr)


@main.command()
def list():
    """List Dangerzone Podman machines."""
    try:
        manager = PodmanMachineManager()
        machines = manager.list()
        if machines:
            for machine in machines:
                running_status = "Running" if machine.get("Running") else "Stopped"
                click.echo(f"Name: {machine.get('Name')}, Status: {running_status}")
        else:
            click.echo("No Dangerzone Podman machines found.")
    except PodmanError as e:
        click.echo(click.style(f"Error: {e}", fg="red"), err=True)
        sys.exit(1)


@main.command()
@click.option("--cpus", type=int, help="Number of CPUs to allocate.")
@click.option("--memory", type=int, help="Amount of memory in bytes.")
@click.option("--timezone", type=str, help="Timezone for the machine.")
def init(cpus, memory, timezone):
    """Initialize a Dangerzone Podman machine."""
    try:
        manager = PodmanMachineManager()
        manager.init(cpus=cpus, memory=memory, timezone=timezone)
        click.echo(f"Machine initialized: {manager.name}")
    except PodmanError as e:
        click.echo(click.style(f"Error: {e}", fg="red"), err=True)
        sys.exit(1)


@main.command()
def start():
    """Start the Dangerzone Podman machine."""
    try:
        manager = PodmanMachineManager()
        manager.start()
        click.echo(f"Machine started: {manager.name}")
    except PodmanError as e:
        click.echo(click.style(f"Error: {e}", fg="red"), err=True)
        sys.exit(1)


@main.command()
def stop():
    """Stop the Dangerzone Podman machine."""
    try:
        manager = PodmanMachineManager()
        manager.stop()
        click.echo(f"Machine stopped: {manager.name}")
    except PodmanError as e:
        click.echo(click.style(f"Error: {e}", fg="red"), err=True)
        sys.exit(1)


@main.command()
@click.option("-f", "--force", is_flag=True, help="Force removal without prompt.")
def remove(force):
    """Remove the Dangerzone Podman machine."""
    try:
        manager = PodmanMachineManager()
        if not force:
            click.confirm(
                f"Are you sure you want to remove machine '{manager.name}'?",
                abort=True,
            )
        manager.remove()
        click.echo(f"Machine removed: {manager.name}")
    except PodmanError as e:
        click.echo(click.style(f"Error: {e}", fg="red"), err=True)
        sys.exit(1)
    except click.exceptions.Abort:
        click.echo("Aborted.")


@main.command()
@click.option("-f", "--force", is_flag=True, help="Force reset without prompt.")
def reset(force):
    """Reset all Podman machines."""
    try:
        if not force:
            click.confirm(
                "Are you sure you want to reset all Podman machines? This is a destructive action.",
                abort=True,
            )
        manager = PodmanMachineManager()
        manager.reset()
        click.echo("Podman machines reset.")
    except PodmanError as e:
        click.echo(click.style(f"Error: {e}", fg="red"), err=True)
        sys.exit(1)
    except click.exceptions.Abort:
        click.echo("Aborted.")


@main.command(context_settings=dict(ignore_unknown_options=True, allow_extra_args=True))
@click.pass_context
def raw(ctx):
    """Run a raw Podman command."""
    try:
        manager = PodmanMachineManager()
        output = manager.run_raw_podman_command(ctx.args)
        if isinstance(output, str):
            click.echo(output)
        else:
            click.echo("Raw command executed.")  # For subprocess.Popen objects
    except PodmanError as e:
        click.echo(click.style(f"Error: {e}", fg="red"), err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
