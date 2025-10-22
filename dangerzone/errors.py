import functools
import logging
import sys
from typing import Any, Callable, TypeVar, cast

import click

F = TypeVar("F", bound=Callable[..., Any])

log = logging.getLogger(__name__)


class DocumentFilenameException(Exception):
    """Exception for document-related filename errors."""


class AddedDuplicateDocumentException(DocumentFilenameException):
    """Exception for a document is added twice."""

    def __init__(self) -> None:
        super().__init__("A document was added twice")


class InputFileNotFoundException(DocumentFilenameException):
    """Exception for when an input file does not exist."""

    def __init__(self) -> None:
        super().__init__("Input file not found: make sure you typed it correctly.")


class InputFileNotReadableException(DocumentFilenameException):
    """Exception for when an input file exists but is not readable."""

    def __init__(self) -> None:
        super().__init__("You don't have permission to open the input file.")


class NonPDFOutputFileException(DocumentFilenameException):
    """Exception for when the output file is not a PDF."""

    def __init__(self) -> None:
        super().__init__("Safe PDF filename must end in '.pdf'")


class IllegalOutputFilenameException(DocumentFilenameException):
    """Exception for when the output file contains illegal characters."""

    def __init__(self, char: str) -> None:
        super().__init__(f"Illegal character: {char}")


class UnwriteableOutputDirException(DocumentFilenameException):
    """Exception for when the output file is not writeable."""

    def __init__(self) -> None:
        super().__init__("Safe PDF filename is not writable")


class NotSetInputFilenameException(DocumentFilenameException):
    """Exception for when the output filename is set before having an
    associated input file."""

    def __init__(self) -> None:
        super().__init__("Input filename has not been set yet.")


class NotSetOutputFilenameException(DocumentFilenameException):
    """Exception for when the output filename is read before it has been set."""

    def __init__(self) -> None:
        super().__init__("Output filename has not been set yet.")


class NonExistantOutputDirException(DocumentFilenameException):
    """Exception for when the output dir does not exist."""

    def __init__(self) -> None:
        super().__init__("Output directory does not exist")


class OutputDirIsNotDirException(DocumentFilenameException):
    """Exception for when the specified output dir is not actually a dir."""

    def __init__(self) -> None:
        super().__init__("Specified output directory is actually not a directory")


class UnwriteableArchiveDirException(DocumentFilenameException):
    """Exception for when the archive directory cannot be created."""

    def __init__(self) -> None:
        super().__init__(
            "Archive directory for storing unsafe documents cannot be created."
        )


class SuffixNotApplicableException(DocumentFilenameException):
    """Exception for when the suffix cannot be applied to the output filename."""

    def __init__(self) -> None:
        super().__init__("Cannot set a suffix after setting an output filename")


def handle_document_errors(func: F) -> F:
    """Decorator to log document-related errors and exit gracefully."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):  # type: ignore
        try:
            return func(*args, **kwargs)
        except DocumentFilenameException as e:
            if getattr(sys, "dangerzone_dev", False):
                # Show the full traceback only on dev environments.
                msg = "An exception occured while validating a document"
                log.exception(msg)
            click.echo(str(e))
            sys.exit(1)

    return cast(F, wrapper)


#### Container-related errors


class ContainerException(Exception):
    pass


class ImageNotPresentException(ContainerException):
    pass


class MultipleImagesFoundException(ContainerException):
    pass


class ImageInstallationException(ContainerException):
    pass


class NoContainerTechException(ContainerException):
    def __init__(self, container_tech: str) -> None:
        super().__init__(f"{container_tech} is not installed")


class NotAvailableContainerTechException(ContainerException):
    def __init__(self, container_tech: str, error: str) -> None:
        self.error = error
        self.container_tech = container_tech
        super().__init__(f"{container_tech} is not available")


class UnsupportedContainerRuntime(ContainerException):
    pass


class ContainerPullException(ContainerException):
    pass


class OtherMachineRunningError(ContainerException):
    pass
