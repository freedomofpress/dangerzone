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
