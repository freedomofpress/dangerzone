import io
import logging
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, Optional

from colorama import Fore, Style
from PIL import Image, UnidentifiedImageError

from ..conversion import errors
from ..document import Document
from ..util import replace_control_chars

log = logging.getLogger(__name__)

MAX_CONVERSION_LOG_CHARS = 150 * 50  # up to ~150 lines of 50 characters
DOC_TO_PIXELS_LOG_START = "----- DOC TO PIXELS LOG START -----"
DOC_TO_PIXELS_LOG_END = "----- DOC TO PIXELS LOG END -----"
PIXELS_TO_PDF_LOG_START = "----- PIXELS TO PDF LOG START -----"
PIXELS_TO_PDF_LOG_END = "----- PIXELS TO PDF LOG END -----"


class IsolationProvider(ABC):
    """
    Abstracts an isolation provider
    """

    @abstractmethod
    def install(self) -> bool:
        pass

    def convert(
        self,
        document: Document,
        ocr_lang: Optional[str],
        progress_callback: Optional[Callable] = None,
    ) -> None:
        self.progress_callback = progress_callback
        document.mark_as_converting()
        try:
            success = self._convert(document, ocr_lang)
        except errors.ConversionException as e:
            success = False
            self.print_progress_trusted(document, True, str(e), 0)
        except Exception as e:
            success = False
            log.exception(
                f"An exception occurred while converting document '{document.id}'"
            )
            self.print_progress_trusted(document, True, str(e), 0)
        if success:
            document.mark_as_safe()
            if document.archive_after_conversion:
                document.archive()
        else:
            document.mark_as_failed()

    @abstractmethod
    def _convert(
        self,
        document: Document,
        ocr_lang: Optional[str],
    ) -> bool:
        pass

    def _print_progress(
        self, document: Document, error: bool, text: str, percentage: float
    ) -> None:
        s = Style.BRIGHT + Fore.YELLOW + f"[doc {document.id}] "
        s += Fore.CYAN + f"{percentage}% " + Style.RESET_ALL
        if error:
            s += Fore.RED + text + Style.RESET_ALL
            log.error(s)
        else:
            s += text
            log.info(s)

        if self.progress_callback:
            self.progress_callback(error, text, percentage)

    def print_progress_trusted(
        self, document: Document, error: bool, text: str, percentage: float
    ) -> None:
        return self._print_progress(document, error, text, int(percentage))

    def print_progress(
        self, document: Document, error: bool, untrusted_text: str, percentage: float
    ) -> None:
        text = replace_control_chars(untrusted_text)
        return self.print_progress_trusted(
            document, error, "UNTRUSTED> " + text, percentage
        )

    @abstractmethod
    def get_max_parallel_conversions(self) -> int:
        pass

    def sanitize_conversion_str(self, untrusted_conversion_str: str) -> str:
        conversion_string = replace_control_chars(untrusted_conversion_str)

        # Add armor (gpg-style)
        armor_start = f"{DOC_TO_PIXELS_LOG_START}\n"
        armor_end = DOC_TO_PIXELS_LOG_END
        return armor_start + conversion_string + armor_end

    def convert_pixels_to_png(
        self, tempdir: str, page: int, width: int, height: int, rgb_data: bytes
    ) -> None:
        """
        Reconstruct PPM files and save as PNG to save space
        """
        if not (1 <= width <= errors.MAX_PAGE_WIDTH):
            raise errors.MaxPageWidthException()
        if not (1 <= height <= errors.MAX_PAGE_HEIGHT):
            raise errors.MaxPageHeightException()

        ppm_header = f"P6\n{width} {height}\n255\n".encode()
        ppm_data = io.BytesIO(ppm_header + rgb_data)
        png_path = Path(tempdir) / f"page-{page}.png"

        # Verify the exact data was received
        if len(rgb_data) != width * height * 3:
            raise errors.InterruptedConversion()

        try:
            Image.open(ppm_data).save(png_path, "PNG")
        except UnidentifiedImageError as e:
            raise errors.PPMtoPNGError() from e
