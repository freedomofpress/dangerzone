import datetime
import enum
import logging
import time
from typing import Callable

from colorama import Fore, Style

from .document import Document

log = logging.getLogger(__name__)


class ConversionCtx:

    EST_PERCENT_START_CONVERSION_PROC = 1
    EST_PERCENT_GATHER_PAGES = 2
    EST_PERCENT_CONVERT_PAGES = 96
    EST_PERCENT_COMPLETE_CONVERSION = 1

    MSG_CONVERSION_PROCESS_TYPE = "process"

    # Conversion state
    STATE_NOT_STARTED = enum.auto()
    STATE_STARTING_CONVERSION_PROC = enum.auto()
    STATE_GATHERING_PAGES = enum.auto()
    STATE_CONVERTING_PAGES = enum.auto()
    STATE_COMPLETED = enum.auto()
    STATE_FAILED = enum.auto()

    def __init__(
        self,
        document: Document,
        ocr_lang: str | None = None,
        progress_callback: Callable | None = None,
    ) -> None:
        self.doc = document
        self.ocr_lang = ocr_lang
        self.callback = progress_callback

        conversion_total = 100  # FiXME:
        assert conversion_total == 100

        self.percentage: float = 0.0
        self.cur_page = 0
        self.pages = 0
        self.page_timer_start = None
        self.state = self.STATE_NOT_STARTED

    def is_not_started(self) -> bool:
        return self.state is self.STATE_NOT_STARTED

    def is_started(self) -> bool:
        return self.state in (
            self.STATE_STARTING_CONVERSION_PROC,
            self.STATE_GATHERING_PAGES,
            self.STATE_CONVERTING_PAGES,
        )

    def is_completed(self) -> bool:
        return self.state is Document.STATE_COMPLETED

    def is_failed(self) -> bool:
        return self.state is Document.STATE_FAILED

    def increase(self, step: float) -> None:
        assert step > 0
        self.percentage += step

    def print_message(self, text: str, error: bool = False) -> None:
        s = Style.BRIGHT + Fore.YELLOW + f"[doc {self.doc.id}] "
        s += Fore.CYAN + f"{int(self.percentage)}% " + Style.RESET_ALL
        if error:
            s += Fore.RED + text + Style.RESET_ALL
            log.error(s)
        else:
            s += text
            log.info(s)

        if self.callback:
            self.callback(error, text, self.percentage)

    def start_conversion_proc(self):
        self.state = self.STATE_STARTING_CONVERSION_PROC
        self.print_message(
            f"Starting a {self.MSG_CONVERSION_PROCESS_TYPE} for the document conversion"
        )

    def start_page_gathering(self):
        self.state = self.STATE_GATHERING_PAGES
        self.increase(self.EST_PERCENT_START_CONVERSION_PROC)
        self.print_message("Getting number of pages")

    def set_total_pages(self, pages: int) -> None:
        self.state = self.STATE_CONVERTING_PAGES
        self.increase(self.EST_PERCENT_GATHER_PAGES)
        assert pages > 0
        self.pages = pages

    def page_iter(self, pages):
        self.set_total_pages(pages)
        for page in range(1, pages + 1):
            self.start_converting_page(page)
            yield page
            self.finished_converting_page()

    def start_converting_page(self, page: int) -> None:
        searchable = "searchable " if self.ocr_lang else ""
        remaining = ""

        if not self.page_timer_start:
            self.page_timer_start = time.monotonic()
        else:
            processed_pages = page - 1
            elapsed = time.monotonic() - self.page_timer_start
            elapsed_per_page = elapsed / processed_pages
            remaining = (self.pages - processed_pages) * elapsed_per_page
            remaining = datetime.timedelta(seconds=round(remaining))
            remaining = f" (remaining: {remaining}s)"

        self.print_message(
            f"Converting page {page}/{self.pages} from pixels to {searchable}PDF{remaining}"
        )

    def finished_converting_page(self) -> None:
        self.increase(self.EST_PERCENT_CONVERT_PAGES / self.pages)

    def fail(self, msg: str) -> None:
        self.state = self.STATE_FAILED
        self.print_message(msg, error=True)
        self.doc.mark_as_failed()

    def success(self) -> None:
        self.state = self.STATE_COMPLETED
        self.percentage = 100
        self.doc.mark_as_safe()
        self.print_message("Conversion completed successfully")
