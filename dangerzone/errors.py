import functools
import logging
import sys
from typing import Any, Callable, Sequence, TypeVar, cast

import click

F = TypeVar("F", bound=Callable[..., Any])

log = logging.getLogger(__name__)


class DocumentFilenameException(Exception):
    """Exception for document-related filename errors."""


def handle_document_errors(func: F) -> F:
    """Log document-related errors and exit gracefully."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):  # type: ignore
        try:
            return func(*args, **kwargs)
        except DocumentFilenameException as e:
            if getattr(sys, "dangerzone_dev", False):
                # Show the full traceback only on dev environments.
                msg = "An exception occured while validating a document filename"
                log.exception(msg)
            click.echo(str(e))
            exit(1)

    return cast(F, wrapper)
