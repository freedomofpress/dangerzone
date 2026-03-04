import argparse
import logging
import subprocess
import sys
from typing import Callable, Optional, List

from ..conversion.common import DangerzoneConverter
from ..document import Document
from .base import IsolationProvider, terminate_process_group

log = logging.getLogger(__name__)


def dummy_script() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs="?")
    parser.add_argument("path", nargs="?")
    args = parser.parse_args()

    if args.command == "index":
        sys.stdin.buffer.read()
        # Report 1 file
        DangerzoneConverter._write_int(1)
        filename = b"/tmp/dummy_file"
        DangerzoneConverter._write_int(len(filename))
        DangerzoneConverter._write_bytes(filename)
    elif args.command == "sanitize":
        pages = 2
        width = height = 9
        DangerzoneConverter._write_int(pages)
        for page in range(pages):
            DangerzoneConverter._write_int(width)
            DangerzoneConverter._write_int(height)
            DangerzoneConverter._write_bytes(width * height * 3 * b"A")
    else:
        # Backwards compatibility
        sys.stdin.buffer.read()
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

    @staticmethod
    def requires_install() -> bool:
        return False

    def start_doc_to_pixels_sandbox(self, document: Document) -> subprocess.Popen:
        # For dummy, we can just start a sleep process or another dummy process.
        # We use a long sleep so that it stays up during the multiple exec calls.
        return subprocess.Popen(
            ["sleep", "1000"],
            stdin=subprocess.PIPE,
            start_new_session=True,
        )

    def start_exec(
        self,
        document: Document,
        command: List[str],
        stdin: Optional[int] = subprocess.PIPE,
    ) -> subprocess.Popen:
        cmd = [
            sys.executable,
            "-c",
            "from dangerzone.isolation_provider.dummy import dummy_script;"
            " dummy_script()",
        ] + command
        return subprocess.Popen(
            cmd,
            stdin=stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )

    def terminate_doc_to_pixels_sandbox(
        self, document: Document, p: subprocess.Popen
    ) -> None:
        from .base import kill_process_group
        kill_process_group(p)

    def get_max_parallel_conversions(self) -> int:
        return 1
