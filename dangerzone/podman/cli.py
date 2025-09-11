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
def main(log_level: str) -> None:
    """Manage Dangerzone Podman machines."""
    logging.basicConfig(level=getattr(logging, log_level.upper()), stream=sys.stderr)


@main.command()
def list() -> None:
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
        click.echo(f"❌ {e}")
        raise click.Abort()


@main.command()
@click.option("--cpus", type=int, help="Number of CPUs to allocate.")
@click.option("--memory", type=int, help="Amount of memory in bytes.")
@click.option(
    "--timezone", type=str, default="Etc/UTC", help="Timezone for the machine."
)
def init(cpus: int, memory: int, timezone: str) -> None:
    """Initialize a Dangerzone Podman machine."""
    try:
        manager = PodmanMachineManager()
        manager.init(cpus=cpus, memory=memory, timezone=timezone)
        click.echo(f"Machine initialized: {manager.name}")
    except PodmanError as e:
        click.echo(f"❌ {e}")
        raise click.Abort()


@main.command()
def start() -> None:
    """Start the Dangerzone Podman machine."""
    try:
        manager = PodmanMachineManager()
        manager.start()
        click.echo(f"Machine started: {manager.name}")
    except PodmanError as e:
        click.echo(f"❌ {e}")
        raise click.Abort()


@main.command()
def stop() -> None:
    """Stop the Dangerzone Podman machine."""
    try:
        manager = PodmanMachineManager()
        manager.stop()
        click.echo(f"Machine stopped: {manager.name}")
    except PodmanError as e:
        click.echo(f"❌ {e}")
        raise click.Abort()


@main.command()
@click.option("-f", "--force", is_flag=True, help="Force removal without prompt.")
def remove(force: bool) -> None:
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
        click.echo(f"❌ {e}")
        raise click.Abort()


@main.command()
@click.option("-f", "--force", is_flag=True, help="Force reset without prompt.")
def reset(force: bool) -> None:
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
        click.echo(f"❌ {e}")
        raise click.Abort()


@main.command(context_settings=dict(ignore_unknown_options=True, allow_extra_args=True))
@click.pass_context
def raw(ctx) -> None:  # type: ignore [no-untyped-def]
    """Run a raw Podman command."""
    try:
        manager = PodmanMachineManager()
        output = manager.run_raw_podman_command(ctx.args)
    except PodmanError as e:
        click.echo(f"❌ {e}")
        raise click.Abort()


if __name__ == "__main__":
    main()
