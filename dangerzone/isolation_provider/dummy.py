import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, Optional

from ..document import Document
from ..util import get_resource_path
from .base import IsolationProvider

log = logging.getLogger(__name__)


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

    def install(self) -> bool:
        return True

    def convert(
        self,
        document: Document,
        ocr_lang: Optional[str],
        progress_callback: Optional[Callable] = None,
    ) -> None:
        self.progress_callback = None
        log.debug("Dummy converter started:")
        log.debug(
            f"  - document: {os.path.basename(document.input_filename)} ({document.id})"
        )
        log.debug(f"  - ocr     : {ocr_lang}")
        log.debug("\n(simulating conversion)")
        success = True
        progress = [
            [False, "Converting to PDF using GraphicsMagick", 0.0],
            [False, "Separating document into pages", 3.0],
            [False, "Converting page 1/1 to pixels", 5.0],
            [False, "Converted document to pixels", 50.0],
            [False, "Converting page 1/1 from pixels to PDF", 50.0],
            [False, "Merging 1 pages into a single PDF", 95.0],
            [False, "Compressing PDF", 97.0],
            [False, "Safe PDF created", 100.0],
        ]
        for error, text, percentage in progress:
            self.print_progress(document, error, text, percentage)  # type: ignore [arg-type]
            if error:
                success = False
            time.sleep(0.2)
        if success:
            shutil.copy(
                get_resource_path("dummy_document.pdf"), document.output_filename
            )
        document.mark_as_safe()
        if document.archive_after_conversion:
            document.archive()

    def pixels_to_pdf(
        self, document: Document, tempdir: str, ocr_lang: Optional[str]
    ) -> None:
        pass

    def start_doc_to_pixels_proc(self) -> subprocess.Popen:
        return subprocess.Popen("True")

    def get_max_parallel_conversions(self) -> int:
        return 1
