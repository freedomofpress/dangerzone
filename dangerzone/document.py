import os
import platform
import stat
import tempfile
from typing import Optional

import appdirs

from .errors import DocumentFilenameException

SAFE_EXTENSION = "-safe.pdf"


class Document:
    """Track the state of a single document.

    The Document class is responsible for holding the state of a single
    document, and validating its info.
    """

    def __init__(self, input_filename: str = None) -> None:
        self._input_filename: Optional[str] = None
        self._output_filename: Optional[str] = None

        if input_filename:
            self.input_filename = input_filename

    @staticmethod
    def normalize_filename(filename: str) -> str:
        return os.path.abspath(filename)

    @staticmethod
    def validate_input_filename(filename: str) -> None:
        try:
            open(filename, "rb")
        except FileNotFoundError as e:
            raise DocumentFilenameException(
                "Input file not found: make sure you typed it correctly."
            ) from e
        except PermissionError as e:
            raise DocumentFilenameException(
                "You don't have permission to open the input file."
            ) from e

    @staticmethod
    def validate_output_filename(filename: str) -> None:
        if not filename.endswith(".pdf"):
            raise DocumentFilenameException("Safe PDF filename must end in '.pdf'")
        try:
            with open(filename, "wb"):
                pass
        except PermissionError as e:
            raise DocumentFilenameException("Safe PDF filename is not writable") from e

    @property
    def input_filename(self) -> str:
        if self._input_filename is None:
            raise DocumentFilenameException("Input filename has not been set yet.")
        else:
            return self._input_filename

    @input_filename.setter
    def input_filename(self, filename: str) -> None:
        filename = self.normalize_filename(filename)
        self.validate_input_filename(filename)
        self._input_filename = filename

    @property
    def output_filename(self) -> str:
        if self._output_filename is None:
            raise DocumentFilenameException("Output filename has not been set yet.")
        else:
            return self._output_filename

    @output_filename.setter
    def output_filename(self, filename: str) -> None:
        filename = self.normalize_filename(filename)
        self.validate_output_filename(filename)
        self._output_filename = filename

    def set_default_output_filename(self) -> None:
        self.output_filename = (
            f"{os.path.splitext(self.input_filename)[0]}{SAFE_EXTENSION}"
        )
