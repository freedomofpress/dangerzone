import os
import platform
import selectors
import subprocess
import threading
import time
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from dangerzone import util

from . import sanitized_text, uncommon_text

VERSION_FILE_NAME = "version.txt"


def test_get_resource_path() -> None:
    share_dir = Path("share").resolve()
    resource_path = Path(util.get_resource_path(VERSION_FILE_NAME)).parent
    assert share_dir.samefile(
        resource_path
    ), f"{share_dir} is not the same file as {resource_path}"


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows-specific")
def test_get_subprocess_startupinfo() -> None:
    startupinfo = util.get_subprocess_startupinfo()
    assert isinstance(startupinfo, subprocess.STARTUPINFO)  # type: ignore[attr-defined]


def test_replace_control_chars(uncommon_text: str, sanitized_text: str) -> None:
    """Test that the replace_control_chars() function works properly."""
    assert util.replace_control_chars(uncommon_text) == sanitized_text
    assert util.replace_control_chars("normal text") == "normal text"
    assert util.replace_control_chars("") == ""


@pytest.mark.skipif(
    platform.system() == "Windows", reason="Cannot test non-blocking read on Windows"
)
def test_nonblocking_read(mocker: MockerFixture) -> None:
    """Test that the nonblocking_read() function works properly."""
    size = 9
    timeout = 1
    r, w = os.pipe()

    # Test 1 - Check that invalid arguments (blocking fd, negative size/timeout ) raise
    # an exception.
    with pytest.raises(ValueError, match="Expected a non-blocking file descriptor"):
        util.nonblocking_read(r, size, timeout)

    os.set_blocking(r, False)

    with pytest.raises(ValueError, match="Expected a positive size value"):
        util.nonblocking_read(r, 0, timeout)

    with pytest.raises(ValueError, match="Expected a positive timeout value"):
        util.nonblocking_read(r, size, 0)

    # Test 2 - Check that partial reads are retried, for the timeout's duration,
    # and we never read more than we want.
    select_spy = mocker.spy(selectors.DefaultSelector, "select")
    read_spy = mocker.spy(os, "read")

    # Write "1234567890", with a delay of 0.3 seconds.
    os.write(w, b"12345")

    def write_rest() -> None:
        time.sleep(0.3)
        os.write(w, b"67890")

    threading.Thread(target=write_rest).start()

    # Ensure that we receive all the characters, except for the last one ("0"), since it
    # exceeds the requested size.
    assert util.nonblocking_read(r, size, timeout) == b"123456789"

    # Ensure that the read/select calls were retried.
    # FIXME: The following asserts are racy, and assume that a 0.3 second delay will
    # trigger a re-read. If our tests fail due to it, we should find a smarter way to
    # test it.
    assert read_spy.call_count == 2
    assert read_spy.call_args_list[0].args[1] == 9
    assert read_spy.call_args_list[1].args[1] == 4
    assert read_spy.spy_return == b"6789"

    assert select_spy.call_count == 2
    timeout1 = select_spy.call_args_list[0].args[1]
    timeout2 = select_spy.call_args_list[1].args[1]
    assert 1 > timeout1 > timeout2

    # Test 3 - Check that timeouts work, even when we partially read something.
    select_spy.reset_mock()
    read_spy.reset_mock()

    # Ensure that the function raises a timeout error.
    with pytest.raises(TimeoutError):
        util.nonblocking_read(r, size, 0.1)

    # Ensure that the function has read a single character from the previous write
    # operation.
    assert read_spy.call_count == 1
    assert read_spy.spy_return == b"0"

    # Ensure that the select() method has been called twice, and that the second time it
    # returned an empty list (meaning that timeout expired).
    assert select_spy.call_count == 2
    assert select_spy.spy_return == []
    timeout1 = select_spy.call_args_list[0].args[1]
    timeout2 = select_spy.call_args_list[1].args[1]
    assert 0.1 > timeout1 > timeout2

    # Test 4 - Check that EOF is detected.
    buf = b"Bye!"
    os.write(w, buf)
    os.close(w)
    assert util.nonblocking_read(r, size, timeout) == buf
