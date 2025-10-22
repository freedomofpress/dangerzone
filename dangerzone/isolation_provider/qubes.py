import io
import logging
import os
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import IO, Callable, Optional

from ..conversion.common import running_on_qubes
from ..document import Document
from ..util import get_resource_path
from .base import IsolationProvider

log = logging.getLogger(__name__)


class Qubes(IsolationProvider):
    """Uses a disposable qube for performing the conversion"""

    @staticmethod
    def requires_install() -> bool:
        return False

    def get_max_parallel_conversions(self) -> int:
        return 1

    def start_doc_to_pixels_proc(self, document: Document) -> subprocess.Popen:
        dev_mode = getattr(sys, "dangerzone_dev", False) is True
        if dev_mode:
            # Use dz.ConvertDev RPC call instead, if we are in development mode.
            # Basically, the change is that we also transfer the necessary Python
            # code as a zipfile, before sending the doc that the user requested.
            qrexec_policy = "dz.ConvertDev"
            stderr = subprocess.PIPE
        else:
            qrexec_policy = "dz.Convert"
            stderr = subprocess.DEVNULL

        p = subprocess.Popen(
            ["/usr/bin/qrexec-client-vm", "@dispvm:dz-dvm", qrexec_policy],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=stderr,
            # Start the conversion process in a new session, so that we can later on
            # kill the process group, without killing the controlling script.
            start_new_session=True,
        )

        if dev_mode:
            assert p.stdin is not None
            # Send the dangerzone module first.
            self.teleport_dz_module(p.stdin)

        return p

    def terminate_doc_to_pixels_proc(
        self, document: Document, p: subprocess.Popen
    ) -> None:
        """Terminate a spawned disposable qube.

        Qubes does not offer a way out of the box to terminate disposable Qubes from
        domU [1]. Our best bet is to close the standard streams of the process, and hope
        that the disposable qube will attempt to read/write to them, and thus receive an
        EOF.

        There are two ways we can do the above; close the standard streams explicitly,
        or terminate the process. The problem with the latter is that terminating
        `qrexec-client-vm` happens immediately, and we no longer have a way to learn if
        the disposable qube actually terminated. That's why we prefer closing the
        standard streams explicitly, so that we can afterwards use `Popen.wait()` to
        learn if the qube terminated.

        Note that we don't close the stderr stream because we want to read debug logs
        from it. In the rare case where a qube cannot terminate because it's stuck
        writing at stderr (this is not the expected behavior), we expect that the
        process will still be forcefully killed after the soft termination timeout
        expires.

        [1]: https://github.com/freedomofpress/dangerzone/issues/563#issuecomment-2034803232
        """
        if p.stdin:
            p.stdin.close()
        if p.stdout:
            p.stdout.close()

    def teleport_dz_module(self, wpipe: IO[bytes]) -> None:
        """Send the dangerzone module to another qube, as a zipfile."""
        # Grab the absolute file path of the dangerzone module.
        import dangerzone as _dz

        _conv_path = Path(_dz.conversion.__file__).parent
        _src_root = Path(_dz.__file__).parent.parent
        temp_file = io.BytesIO()

        with zipfile.ZipFile(temp_file, "w") as z:
            z.mkdir("dangerzone/")
            z.writestr("dangerzone/__init__.py", "")
            for root, _, files in os.walk(_conv_path):
                for file in files:
                    if file.endswith(".py"):
                        file_path = os.path.join(root, file)
                        relative_path = os.path.relpath(file_path, _src_root)
                        z.write(file_path, relative_path)

        # Send the following data:
        # 1. The size of the Python zipfile, so that the server can know when to
        #    stop.
        # 2. The Python zipfile itself.
        bufsize_bytes = len(temp_file.getvalue()).to_bytes(4, "big")
        wpipe.write(bufsize_bytes)
        wpipe.write(temp_file.getvalue())


def is_qubes_native_conversion() -> bool:
    """Returns True if the conversion should be run using Qubes OS's diposable
    VMs and False if not."""
    if running_on_qubes():
        if getattr(sys, "dangerzone_dev", False):
            return os.environ.get("QUBES_CONVERSION", "0") == "1"

        # XXX If Dangerzone is installed check if container image was shipped
        # This disambiguates if it is running a Qubes targetted build or not
        # (Qubes-specific builds don't ship the container image)

        return not get_resource_path("container.tar").exists()
    else:
        return False
