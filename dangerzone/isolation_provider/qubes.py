import asyncio
import inspect
import io
import logging
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import IO, Callable, Optional

from ..conversion import errors
from ..conversion.common import running_on_qubes
from ..document import Document
from ..util import get_resource_path
from .base import IsolationProvider

log = logging.getLogger(__name__)


class Qubes(IsolationProvider):
    """Uses a disposable qube for performing the conversion"""

    def install(self) -> bool:
        return True

    def get_max_parallel_conversions(self) -> int:
        return 1

    def start_doc_to_pixels_proc(self) -> subprocess.Popen:
        dev_mode = getattr(sys, "dangerzone_dev", False) == True
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
        )

        if dev_mode:
            assert p.stdin is not None
            # Send the dangerzone module first.
            self.teleport_dz_module(p.stdin)

        return p

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
            import dangerzone.conversion

            conv_path = Path(dangerzone.conversion.__file__).parent
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
    """Returns True if the conversion should be run using Qubes OS's disposable
    VMs and False if not."""
    if running_on_qubes():
        if getattr(sys, "dangerzone_dev", False):
            return os.environ.get("QUBES_CONVERSION", "0") == "1"

        # XXX If Dangerzone is installed check if container image was shipped
        # This disambiguates if it is running a Qubes targetted build or not
        # (Qubes-specific builds don't ship the container image)

        compressed_container_path = get_resource_path("container.tar.gz")
        return not os.path.exists(compressed_container_path)
    else:
        return False
