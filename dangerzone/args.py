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
    filename = Document.normalize_filename(value)
    Document.validate_input_filename(filename)
    return filename


@errors.handle_document_errors
def validate_output_filename(
    ctx: click.Context, param: str, value: Optional[str]
) -> Optional[str]:
    if value is None:
        return None
    filename = Document.normalize_filename(value)
    Document.validate_output_filename(filename)
    return filename
