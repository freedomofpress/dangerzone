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
        self.input_filename: Optional[str] = None
        self.output_filename: Optional[str] = None
