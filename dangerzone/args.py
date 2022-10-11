from typing import Optional

import click

from . import errors
from .document import Document


@errors.handle_document_errors
def validate_input_filename(
    ctx: click.Context, param: str, value: Optional[str]
) -> Optional[str]:
    if value is None:
        return None
    Document.validate_input_filename(value)
    return value


@errors.handle_document_errors
def validate_output_filename(
    ctx: click.Context, param: str, value: Optional[str]
) -> Optional[str]:
    if value is None:
        return None
    Document.validate_output_filename(value)
    return value
