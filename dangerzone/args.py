import functools
import os
from typing import List, Optional, Tuple

import click

from . import errors
from .document import Document


@errors.handle_document_errors
def _validate_input_filename(
    ctx: click.Context, param: str, value: Optional[str]
) -> Optional[str]:
    if value is None:
        return None
    filename = Document.normalize_filename(value)
    Document.validate_input_filename(filename)
    return filename


@errors.handle_document_errors
def _validate_input_filenames(
    ctx: click.Context, param: List[str], value: Tuple[str]
) -> List[str]:
    normalized_filenames = []
    for filename in value:
        filename = Document.normalize_filename(filename)
        Document.validate_input_filename(filename)
        normalized_filenames.append(filename)
    return normalized_filenames


@errors.handle_document_errors
def _validate_output_filename(
    ctx: click.Context, param: str, value: Optional[str]
) -> Optional[str]:
    if value is None:
        return None
    filename = Document.normalize_filename(value)
    Document.validate_output_filename(filename)
    return filename


# XXX: Click versions 7.x and below inspect the number of arguments that the
# callback handler supports. Unfortunately, common Python decorators (such as
# `handle_document_errors()`) mask this number, so we need to reinstate it
# somehow [1]. The simplest way to do so is using a wrapper function.
#
# Once we stop supporting Click 7.x, we can remove the wrappers below.
#
# [1]: https://github.com/freedomofpress/dangerzone/issues/206#issuecomment-1297336863
def validate_input_filename(
    ctx: click.Context, param: str, value: Optional[str]
) -> Optional[str]:
    return _validate_input_filename(ctx, param, value)


def validate_input_filenames(
    ctx: click.Context, param: List[str], value: Tuple[str]
) -> List[str]:
    return _validate_input_filenames(ctx, param, value)


def validate_output_filename(
    ctx: click.Context, param: str, value: Optional[str]
) -> Optional[str]:
    return _validate_output_filename(ctx, param, value)


def check_suspicious_options(args: List[str]) -> None:
    options = set([arg for arg in args if arg.startswith("-")])
    try:
        files = set(os.listdir())
    except Exception:
        # If we can list files in the current working directory, this means that
        # we're probably in an unlinked directory. Dangerzone should still work in
        # this case, so we should return here.
        return

    intersection = options & files
    if intersection:
        filenames_str = ", ".join(intersection)
        msg = (
            f"Security: Detected CLI options that are also present as files in the"
            f" current working directory: {filenames_str}"
        )
        click.echo(msg)
        exit(1)


def override_parser_and_check_suspicious_options(click_main: click.Command) -> None:
    """Override the argument parsing logic of Click.

    Click does not allow us to have access to the raw arguments that it receives (either
    from sys.argv or from its testing module). To circumvent this, we can override its
    `Command.parse_args()` method, which is public and should be safe to do so.

    We can use it to check for any suspicious options prior to arg parsing.
    """
    orig_parse_fn = click_main.parse_args

    @functools.wraps(orig_parse_fn)
    def custom_parse_fn(ctx: click.Context, args: List[str]) -> List[str]:
        check_suspicious_options(args)
        return orig_parse_fn(ctx, args)

    click_main.parse_args = custom_parse_fn  # type: ignore [assignment]
