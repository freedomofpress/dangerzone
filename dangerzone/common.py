import os
import platform
import stat
import tempfile
from typing import Optional

import appdirs


class Common(object):
    """
    The Common class is a singleton of shared functionality throughout an open dangerzone window
    """

    def __init__(self) -> None:
        # Name of input and out files
        self._input_filename: Optional[str] = None
        self._output_filename: Optional[str] = None

    @property
    def input_filename(self) -> str:
        if self._input_filename is None:
            raise RuntimeError("Input filename has not been set yet.")
        else:
            return self._input_filename

    @input_filename.setter
    def input_filename(self, filename: str) -> None:
        self._input_filename = filename

    @property
    def output_filename(self) -> str:
        if self._output_filename is None:
            raise RuntimeError("Output filename has not been set yet.")
        else:
            return self._output_filename

    @output_filename.setter
    def output_filename(self, filename: str) -> None:
        self._output_filename = filename