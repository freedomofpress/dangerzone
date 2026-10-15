import functools
import pathlib
import sys

import click

from . import errors, util
from .document import Document

STDIO_DESCRIPTOR = "-"


@errors.handle_document_errors
def validate_input_filenames(
    ctx: click.Context, param: list[str], value: tuple[str]
) -> list[str]:
    normalized_filenames = []
    for filename in value:
        if filename != STDIO_DESCRIPTOR:
            filename = Document.normalize_filename(filename)
            Document.validate_input_filename(filename)
        normalized_filenames.append(filename)
    return normalized_filenames


@errors.handle_document_errors
def validate_output_filename(
    ctx: click.Context, param: str, value: str | None
) -> str | None:
    if value is None:
        return None
    if value == STDIO_DESCRIPTOR:
        # Writing the safe PDF to stdout. There is no filename to normalize or
        # validate in this case.
        return value
    filename = Document.normalize_filename(value)
    Document.validate_output_filename(filename)
    return filename


def get_known_options(ctx: click.Context) -> set[str]:
    """Collect every option name that the command being parsed accepts.

    Instead of keeping a hardcoded list of our flags, we ask Click for them. Each
    `click.Option` knows its own spellings through `opts` and `secondary_opts`
    (e.g. `--archive`, `-o`).
    """
    return {
        name
        for param in ctx.command.params
        for name in (*param.opts, *param.secondary_opts)
    }


def check_suspicious_options(args: list[str], known_options: set[str]) -> None:
    for arg in args:
        # Check if a provided argument matches our CLI command options, **and** a file
        # in the current working directory. Take options like --opt=val into account as
        # well.
        if arg.split("=", 1)[0] in known_options and pathlib.Path(arg).exists():
            msg = (
                "Security: Detected CLI options that are also present as files in the"
                f" current working directory: {util.replace_control_chars(arg)}"
            )
            click.echo(msg)
            sys.exit(1)


def override_parser_and_check_suspicious_options(click_main: click.Command) -> None:
    """Override the argument parsing logic of Click.

    Click does not allow us to have access to the raw arguments that it receives (either
    from sys.argv or from its testing module). To circumvent this, we can override its
    `Command.parse_args()` method, which is public and should be safe to do so.

    We can use it to check, prior to arg parsing, whether any of the received arguments
    is a file impersonating one of the options that this command accepts.
    """
    orig_parse_fn = click_main.parse_args

    @functools.wraps(orig_parse_fn)
    def custom_parse_fn(ctx: click.Context, args: list[str]) -> list[str]:
        check_suspicious_options(args, get_known_options(ctx))
        return orig_parse_fn(ctx, args)

    click_main.parse_args = custom_parse_fn  # type: ignore [method-assign]
