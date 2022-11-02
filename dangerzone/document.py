import enum
import logging
import os
import platform
import secrets
import stat
import tempfile
from pathlib import Path
from typing import Optional

import appdirs

from . import errors

SAFE_EXTENSION = "-safe.pdf"

log = logging.getLogger(__name__)


class Document:
    """Track the state of a single document.

    The Document class is responsible for holding the state of a single
    document, and validating its info.
    """

    # document conversion state
    STATE_UNCONVERTED = enum.auto()
    STATE_CONVERTING = enum.auto()
    STATE_SAFE = enum.auto()
    STATE_FAILED = enum.auto()

    def __init__(self, input_filename: str = None, output_filename: str = None) -> None:
        # NOTE: See https://github.com/freedomofpress/dangerzone/pull/216#discussion_r1015449418
        self.id = secrets.token_urlsafe(6)[0:6]

        self._input_filename: Optional[str] = None
        self._output_filename: Optional[str] = None

        if input_filename:
            self.input_filename = input_filename
            self.announce_id()

            if output_filename:
                self.output_filename = output_filename

        self.state = Document.STATE_UNCONVERTED

    @staticmethod
    def normalize_filename(filename: str) -> str:
        return os.path.abspath(filename)

    @staticmethod
    def validate_input_filename(filename: str) -> None:
        try:
            open(filename, "rb")
        except FileNotFoundError as e:
            raise errors.InputFileNotFoundException() from e
        except PermissionError as e:
            raise errors.InputFileNotReadableException() from e

    @staticmethod
    def validate_output_filename(filename: str) -> None:
        if not filename.endswith(".pdf"):
            raise errors.NonPDFOutputFileException()
        if not os.access(Path(filename).parent, os.W_OK):
            # in unwriteable directory
            raise errors.UnwriteableOutputDirException()

    @property
    def input_filename(self) -> str:
        if self._input_filename is None:
            raise errors.NotSetInputFilenameException()
        else:
            return self._input_filename

    @input_filename.setter
    def input_filename(self, filename: str) -> None:
        filename = self.normalize_filename(filename)
        self.validate_input_filename(filename)
        self._input_filename = filename
        self.announce_id()

    @property
    def output_filename(self) -> str:
        if self._output_filename is None:
            if self._input_filename is not None:
                return self.default_output_filename
            else:
                raise errors.NotSetOutputFilenameException()
        else:
            return self._output_filename

    @output_filename.setter
    def output_filename(self, filename: str) -> None:
        filename = self.normalize_filename(filename)
        self.validate_output_filename(filename)
        self._output_filename = filename

    @property
    def default_output_filename(self) -> str:
        return f"{os.path.splitext(self.input_filename)[0]}{SAFE_EXTENSION}"

    def announce_id(self) -> None:
        log.info(f"Assigning ID '{self.id}' to doc '{self.input_filename}'")

    def is_unconverted(self) -> bool:
        return self.state is Document.STATE_UNCONVERTED

    def is_converting(self) -> bool:
        return self.state is Document.STATE_CONVERTING

    def is_failed(self) -> bool:
        return self.state is Document.STATE_FAILED

    def is_safe(self) -> bool:
        return self.state is Document.STATE_SAFE

    def mark_as_converting(self) -> None:
        log.debug(f"Marking doc {self.id} as 'converting'")
        self.state = Document.STATE_CONVERTING

    def mark_as_failed(self) -> None:
        log.debug(f"Marking doc {self.id} as 'failed'")
        self.state = Document.STATE_FAILED

    def mark_as_safe(self) -> None:
        log.debug(f"Marking doc {self.id} as 'safe'")
        self.state = Document.STATE_SAFE
