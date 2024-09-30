import logging
import os
import shutil
import subprocess
import sys
import time
from typing import Callable, Optional

from ..document import Document
from ..conversion.common import DangerzoneConverter
from ..document import Document
from ..util import get_resource_path
from .base import IsolationProvider, terminate_process_group

log = logging.getLogger(__name__)


def dummy_script() -> None:
    sys.stdin.read()

    pages = 2
    width = height = 9
    DangerzoneConverter._write_int(pages)
    for page in range(pages):
        DangerzoneConverter._write_int(width)
        DangerzoneConverter._write_int(height)
        DangerzoneConverter._write_bytes(width * height * 3 * b"A")


class Dummy(IsolationProvider):
    """Dummy Isolation Provider (FOR TESTING ONLY)

    "Do-nothing" converter - the sanitized files are the same as the input files.
    Useful for testing without the need to use docker.
    """

    def __init__(self) -> None:
        # Sanity check
        if not getattr(sys, "dangerzone_dev", False):
            raise Exception(
                "Dummy isolation provider is UNSAFE and should never be "
                + "called in a non-testing system."
            )
        super().__init__()

    def install(self) -> bool:
        return True

    def start_doc_to_pixels_proc(self, document: Document) -> subprocess.Popen:
        cmd = [
            "python3",
            "-c",
            "from dangerzone.isolation_provider.dummy import dummy_script;"
            " dummy_script()"
        ]
        return subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self.proc_stderr,
            start_new_session=True
        )

    def terminate_doc_to_pixels_proc(
        self, document: Document, p: subprocess.Popen
    ) -> None:
        terminate_process_group(p)

    def get_max_parallel_conversions(self) -> int:
        return 1
