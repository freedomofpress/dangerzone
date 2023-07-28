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

from . import errors, util

SAFE_EXTENSION = "-safe.pdf"
ARCHIVE_SUBDIR = "unsafe"

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

    def __init__(
        self,
        input_filename: Optional[str] = None,
        output_filename: Optional[str] = None,
        suffix: str = SAFE_EXTENSION,
        archive: bool = False,
    ) -> None:
        # NOTE: See https://github.com/freedomofpress/dangerzone/pull/216#discussion_r1015449418
        self.id = secrets.token_urlsafe(6)[0:6]

        self._input_filename: Optional[str] = None
        self._output_filename: Optional[str] = None
        self._archive = False
        self._suffix = suffix

        if input_filename:
            self.input_filename = input_filename

            if output_filename:
                self.output_filename = output_filename

        self.state = Document.STATE_UNCONVERTED

        self.archive_after_conversion = archive

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

    def validate_default_archive_dir(self) -> None:
        """Checks if archive dir can be created"""
        if not os.access(self.default_archive_dir.parent, os.W_OK):
            raise errors.UnwriteableArchiveDirException()

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
    def suffix(self) -> str:
        return self._suffix

    @suffix.setter
    def suffix(self, suf: str) -> None:
        if self._output_filename is None:
            self._suffix = suf
        else:
            raise errors.SuffixNotApplicableException()

    @property
    def archive_after_conversion(self) -> bool:
        return self._archive

    @archive_after_conversion.setter
    def archive_after_conversion(self, enabled: bool) -> None:
        if enabled:
            self.validate_default_archive_dir()
            self._archive = True
        else:
            self._archive = False

    def archive(self) -> None:
        """
        Moves the original document to a subdirectory. Prevents the user from
        mistakenly opening the unsafe (original) document.
        """
        archive_dir = self.default_archive_dir
        old_file_path = Path(self.input_filename)
        new_file_path = archive_dir / old_file_path.name
        log.debug(f"Archiving doc {self.id} to {new_file_path}")
        Path.mkdir(archive_dir, exist_ok=True)
        old_file_path.rename(new_file_path)

    @property
    def default_archive_dir(self) -> Path:
        return Path(self.input_filename).parent / ARCHIVE_SUBDIR

    @property
    def default_output_filename(self) -> str:
        return f"{os.path.splitext(self.input_filename)[0]}{self.suffix}"

    def announce_id(self) -> None:
        sanitized_filename = util.replace_control_chars(self.input_filename)
        log.info(f"Assigning ID '{self.id}' to doc '{sanitized_filename}'")

    def set_output_dir(self, path: str) -> None:
        # keep the same name
        old_filename = os.path.basename(self.output_filename)

        new_path = os.path.abspath(path)
        if not os.path.exists(new_path):
            raise errors.NonExistantOutputDirException()
        if not os.path.isdir(new_path):
            raise errors.OutputDirIsNotDirException()
        if not os.access(new_path, os.W_OK):
            raise errors.UnwriteableOutputDirException()

        self._output_filename = os.path.join(new_path, old_filename)

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

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Document):
            return False
        return (
            Path(self.input_filename).absolute()
            == Path(other.input_filename).absolute()
        )

    def __hash__(self) -> int:
        return hash(str(Path(self.input_filename).absolute()))

    def __str__(self) -> str:
        return self.input_filename
