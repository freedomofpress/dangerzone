#!/usr/bin/env python3

import asyncio
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time
from abc import abstractmethod
from typing import Callable, Dict, List, Optional, TextIO, Tuple, Union

TIMEOUT_PER_PAGE: float = 30  # (seconds)
TIMEOUT_PER_MB: float = 30  # (seconds)
TIMEOUT_MIN: float = 60  # (seconds)
DEFAULT_DPI = 150  # Pixels per inch


def running_on_qubes() -> bool:
    # https://www.qubes-os.org/faq/#what-is-the-canonical-way-to-detect-qubes-vm
    return os.path.exists("/usr/share/qubes/marker-vm")


def calculate_timeout(size: float, pages: Optional[float] = None) -> float:
    """Calculate the timeout for a command.

    The timeout calculation takes two factors in mind:

    1. The size (in MiBs) of the dataset (document, multiple pages).
    2. The number of pages in the dataset.

    It then calculates proportional timeout values based on the above, and keeps the
    large one.  This way, we can handle several corner cases:

    * Documents with lots of pages, but small file size.
    * Single images with large file size.
    """
    # Do not have timeouts lower than 10 seconds, if the file size is small, since
    # we need to take into account the program's startup time as well.
    timeout = max(TIMEOUT_PER_MB * size, TIMEOUT_MIN)
    if pages:
        timeout = max(timeout, TIMEOUT_PER_PAGE * pages)
    return timeout


def get_tessdata_dir() -> str:
    if running_on_qubes():
        return "/usr/share/tesseract/tessdata/"
    else:
        return "/usr/share/tessdata/"


class DangerzoneConverter:
    def __init__(self, progress_callback: Optional[Callable] = None) -> None:
        self.percentage: float = 0.0
        self.progress_callback = progress_callback
        self.captured_output: bytes = b""

    @classmethod
    def _read_bytes(cls) -> bytes:
        """Read bytes from the stdin."""
        data = sys.stdin.buffer.read()
        if data is None:
            raise EOFError
        return data

    @classmethod
    def _write_bytes(cls, data: bytes, file: TextIO = sys.stdout) -> None:
        file.buffer.write(data)

    @classmethod
    def _write_text(cls, text: str, file: TextIO = sys.stdout) -> None:
        cls._write_bytes(text.encode(), file=file)

    @classmethod
    def _write_int(cls, num: int, file: TextIO = sys.stdout) -> None:
        cls._write_bytes(num.to_bytes(2, signed=False), file=file)

    # ==== ASYNC METHODS ====
    # We run sync methods in async wrappers, because pure async methods are more difficult:
    # https://stackoverflow.com/a/52702646
    #
    # In practice, because they are I/O bound and we don't have many running concurrently,
    # they shouldn't cause a problem.

    @classmethod
    async def read_bytes(cls) -> bytes:
        return await asyncio.to_thread(cls._read_bytes)

    @classmethod
    async def write_bytes(cls, data: bytes, file: TextIO = sys.stdout) -> None:
        return await asyncio.to_thread(cls._write_bytes, data, file=file)

    @classmethod
    async def write_text(cls, text: str, file: TextIO = sys.stdout) -> None:
        return await asyncio.to_thread(cls._write_text, text, file=file)

    @classmethod
    async def write_int(cls, num: int, file: TextIO = sys.stdout) -> None:
        return await asyncio.to_thread(cls._write_int, num, file=file)

    async def read_stream(
        self, sr: asyncio.StreamReader, callback: Optional[Callable] = None
    ) -> bytes:
        """Consume a byte stream line-by-line.

        Read all lines in a stream until EOF. If a user has passed a callback, call it for
        each line.

        Note that the lines are in bytes, since we can't assume that all command output will
        be UTF-8 encoded. Higher level commands are advised to decode the output to Unicode,
        if they know its encoding.
        """
        buf = b""
        while not sr.at_eof():
            line = await sr.readline()
            self.captured_output += line
            if callback is not None:
                await callback(line)
            buf += line
        return buf

    async def run_command(
        self,
        args: List[str],
        *,
        error_message: str,
        timeout_message: Optional[str] = None,
        timeout: Optional[float] = None,
        stdout_callback: Optional[Callable] = None,
        stderr_callback: Optional[Callable] = None,
    ) -> Tuple[bytes, bytes]:
        """Run a command and get its output.

        Run a command using asyncio.subprocess, consume its standard streams, and return its
        output in bytes.

        :raises RuntimeError: if the process returns a non-zero exit status
        :raises TimeoutError: if the process times out
        """
        # Start the provided command, and return a handle. The command will run in the
        # background.
        proc = await asyncio.subprocess.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Log command to debug log so we can trace back which errors
        # are from each command
        self.captured_output += f"[COMMAND] {' '.join(args)}\n".encode()

        assert proc.stdout is not None
        assert proc.stderr is not None

        # Create asynchronous tasks that will consume the standard streams of the command,
        # and call callbacks if necessary.
        stdout_task = asyncio.create_task(
            self.read_stream(proc.stdout, stdout_callback)
        )
        stderr_task = asyncio.create_task(
            self.read_stream(proc.stderr, stderr_callback)
        )

        # Wait until the command has finished, for a specific timeout. Then, verify that the
        # command has completed successfully. In any other case, raise an exception.
        try:
            ret = await asyncio.wait_for(proc.wait(), timeout=timeout)
        except asyncio.exceptions.TimeoutError:
            raise TimeoutError(timeout_message)
        if ret != 0:
            raise RuntimeError(error_message)

        # Wait until the tasks that consume the command's standard streams have exited as
        # well, and return their output.
        stdout = await stdout_task
        stderr = await stderr_task
        return (stdout, stderr)

    def calculate_timeout(
        self, size: float, pages: Optional[float] = None
    ) -> Optional[float]:
        """Calculate the timeout for a command."""
        if not int(os.environ.get("ENABLE_TIMEOUTS", 1)):
            return None

        return calculate_timeout(size, pages)

    @abstractmethod
    async def convert(self) -> None:
        pass

    @abstractmethod
    def update_progress(self, text: str) -> None:
        pass
