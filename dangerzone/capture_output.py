import io
import logging
import shlex
import subprocess
import threading
from io import IOBase
from typing import Any, Union

# This module provides patching utilities to redirect the standard output and
# standard errors to a log that can be displayed inside the application.


log = logging.getLogger()

original_subprocess_run = subprocess.run
original_subprocess_popen = subprocess.Popen


def _decode_if_needed(input: Union[bytes, str]) -> str:
    if type(input) == bytes:
        return input.decode()
    else:
        return str(input)


class PatchedPopen(original_subprocess_popen):
    def __init__(  # type: ignore[no-untyped-def]
        self, *args, **kwargs
    ):
        """Patch the subprocess.Popen to generate log entries:

        - If stdout and stderr are defined, don't alter the behavior ;
        - Otherwise, create PIPEs for stdout and stderr, and then start threads in
          the background to consume stdout and stdin, and pass it to `log.debug()`
        """
        stdout = kwargs.get("stdout")
        stderr = kwargs.get("stderr")
        encoding = kwargs.get("encoding")
        log.info(f"Running: {shlex.join(args[0])}")
        if stdout is not None or stderr is not None:
            super().__init__(*args, **kwargs)
            return

        # Read the stdout and stderr as streams (text=True and bufsize=1)
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.PIPE
        # We want the stream to be line-buffered, which requires these two arguments.
        kwargs["text"] = True
        kwargs["bufsize"] = 1

        super().__init__(*args, **kwargs)

        def _consume_pipe(pipe: IOBase) -> None:
            for line in iter(pipe.readline, ""):
                log.info(_decode_if_needed(line))

        # Create threads to read the stdout and stderr
        thread_out = threading.Thread(target=_consume_pipe, args=(self.stdout,))
        thread_err = threading.Thread(target=_consume_pipe, args=(self.stderr,))

        original_process_poll = self.poll

        # Patch the .poll() method to wait for the threads to finish
        def patched_poll(*args, **kwargs):  # type: ignore[no-untyped-def]
            returncode = original_process_poll(*args, **kwargs)
            if returncode is not None:
                for t in (thread_out, thread_err):
                    t.join()
            return returncode

        self.poll = patched_poll

        # Start the threads
        for t in (thread_out, thread_err):
            t.daemon = True
            t.start()

        # Set process.std{out,err} to None
        # to prevent the original implementation from consuming
        # the pipes in the .communicate() method.
        self.stdout = None
        self.stderr = None


def patched_subprocess_run(  # type: ignore[no-untyped-def]
    *args, **kwargs
) -> subprocess.CompletedProcess:
    """
    Patch subprocess.run to log stdout and stderr and the command that was run.
    """
    try:
        process = original_subprocess_run(
            *args,
            **kwargs,
        )
    except subprocess.CalledProcessError as e:
        log.exception(e)
        raise

    # process.std{out,err} is set to `None` by the patched Popen when reading the
    # streams as it comes. If it is set here, it means it is not logged
    # elsewhere, so do it.
    if process.stdout is not None:
        log.info(_decode_if_needed(process.stdout))
    if process.stderr is not None:
        log.info(_decode_if_needed(process.stderr))

    log.info(f"Process returncode: {process.returncode}")
    return process


def patch_stdlib() -> None:
    """Patch the subprocess.run and subprocess.Popen to log its results using log.debug()"""
    subprocess.run = patched_subprocess_run
    subprocess.Popen = PatchedPopen  # type:ignore
