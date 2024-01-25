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
from ..conversion.pixels_to_pdf import PixelsToPDF
from ..document import Document
from ..util import get_resource_path
from .base import PIXELS_TO_PDF_LOG_END, PIXELS_TO_PDF_LOG_START, IsolationProvider

log = logging.getLogger(__name__)


class Qubes(IsolationProvider):
    """Uses a disposable qube for performing the conversion"""

    def install(self) -> bool:
        return True

    def pixels_to_pdf(
        self, document: Document, tempdir: str, ocr_lang: Optional[str]
    ) -> None:
        def print_progress_wrapper(error: bool, text: str, percentage: float) -> None:
            self.print_progress(document, error, text, percentage)

        converter = PixelsToPDF(progress_callback=print_progress_wrapper)
        try:
            asyncio.run(converter.convert(ocr_lang, tempdir))
        except (RuntimeError, ValueError) as e:
            raise errors.UnexpectedConversionError(str(e))
        finally:
            if getattr(sys, "dangerzone_dev", False):
                out = converter.captured_output.decode()
                text = (
                    f"Conversion output: (pixels to PDF)\n"
                    f"{PIXELS_TO_PDF_LOG_START}\n{out}{PIXELS_TO_PDF_LOG_END}"
                )
                log.info(text)

        shutil.move(f"{tempdir}/safe-output-compressed.pdf", document.output_filename)

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
        import dangerzone.conversion as _conv

        _conv_path = Path(inspect.getfile(_conv)).parent
        temp_file = io.BytesIO()

        # Create a Python zipfile that contains all the files of the dangerzone module.
        with zipfile.PyZipFile(temp_file, "w") as z:
            z.mkdir("dangerzone/")
            z.writestr("dangerzone/__init__.py", "")
            z.writepy(str(_conv_path), basename="dangerzone/")

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

        compressed_container_path = get_resource_path("container.tar.gz")
        return not os.path.exists(compressed_container_path)
    else:
        return False
