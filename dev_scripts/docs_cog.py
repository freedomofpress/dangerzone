"""Helpers for embedding live CLI help output in the documentation.

The reference pages under docs/reference/cli/ contain cog blocks that call the
functions below, so that the documented ``--help`` output is always the one
produced by the code. Regenerate with ``make docs-cog`` and check that the
pages are up to date with ``make docs-cog-check``.

See https://cog.readthedocs.io/ for how cog blocks work.
"""

import click

from dangerzone.cli import run as dangerzone_cli
from dangerzone.podman.cli import main as dangerzone_machine
from dangerzone.updater.cli import run as dangerzone_image

WIDTH = 80

COMMANDS = {
    "dangerzone-cli": dangerzone_cli,
    "dangerzone-image": dangerzone_image,
    "dangerzone-machine": dangerzone_machine,
}


def _context(
    cmd: click.Command, name: str, parent: click.Context | None
) -> click.Context:
    # Use make_context() so that the group's context_settings (such as
    # show_default) apply, exactly as they do when the command runs for real.
    ctx = cmd.make_context(name, [], parent=parent, resilient_parsing=True)
    ctx.terminal_width = WIDTH
    ctx.max_content_width = WIDTH
    return ctx


def _pin_machine_dependent_defaults(cmd: click.Command) -> None:
    # The default of `dangerzone-image prepare-archive --arch` is the
    # architecture of the machine that renders the docs. Show a description
    # instead of a value, so that the generated output does not depend on the
    # machine that ran cog.
    for param in cmd.params:
        if isinstance(param, click.Option) and param.name == "arch":
            param.show_default = "the architecture of the current machine"


def help_text(tool: str, subcommand: str | None = None) -> str:
    """Return the ``--help`` output of a tool, or of one of its subcommands."""
    cmd = COMMANDS[tool]
    ctx = _context(cmd, tool, None)
    if subcommand is None:
        return ctx.get_help()
    assert isinstance(cmd, click.Group)
    sub = cmd.get_command(ctx, subcommand)
    assert sub is not None, f"{tool} has no subcommand {subcommand}"
    _pin_machine_dependent_defaults(sub)
    return _context(sub, subcommand, ctx).get_help()


def subcommands(tool: str) -> list[str]:
    cmd = COMMANDS[tool]
    assert isinstance(cmd, click.Group)
    return cmd.list_commands(_context(cmd, tool, None))


def cli_help(tool: str, subcommand: str | None = None) -> None:
    """Emit a console block with the ``--help`` output, for use in cog blocks."""
    import cog  # Only available while cog runs the block.

    invocation = tool if subcommand is None else f"{tool} {subcommand}"
    cog.outl("```console")
    cog.outl(f"$ {invocation} --help")
    cog.outl(help_text(tool, subcommand).rstrip("\n"))
    cog.outl("```")
