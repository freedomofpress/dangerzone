import concurrent.futures
import json
import logging
from typing import Callable, List, Optional

import colorama

from . import errors, util
from .document import Document
from .isolation_provider.base import IsolationProvider
from .settings import Settings
from .util import get_resource_path

log = logging.getLogger(__name__)


class DangerzoneCore(object):
    """
    Singleton of shared state / functionality throughout the app
    """

    def __init__(self, isolation_provider: IsolationProvider) -> None:
        # Initialize terminal colors
        colorama.init(autoreset=True)

        # App data folder
        self.appdata_path = util.get_config_dir()

        # Languages supported by tesseract
        with open(get_resource_path("ocr-languages.json"), "r") as f:
            unsorted_ocr_languages = json.load(f)
            self.ocr_languages = dict(sorted(unsorted_ocr_languages.items()))

        # Load settings
        self.settings = Settings(self)
        self.documents: List[Document] = []
        self.isolation_provider = isolation_provider

    def add_document_from_filename(
        self,
        input_filename: str,
        output_filename: Optional[str] = None,
        archive: bool = False,
    ) -> None:
        doc = Document(input_filename, output_filename, archive=archive)
        self.add_document(doc)

    def add_document(self, doc: Document) -> None:
        if doc in self.documents:
            raise errors.AddedDuplicateDocumentException()
        self.documents.append(doc)

    def remove_document(self, doc: Document) -> None:
        if doc not in self.documents:
            # Sanity check: should not have reached
            return
        log.debug(f"Removing document {doc.input_filename}")
        self.documents.remove(doc)

    def clear_documents(self) -> None:
        log.debug("Removing all documents")
        self.documents = []

    def convert_documents(
        self, ocr_lang: Optional[str], stdout_callback: Optional[Callable] = None
    ) -> None:
        def convert_doc(document: Document) -> None:
            try:
                self.isolation_provider.convert(
                    document,
                    ocr_lang,
                    stdout_callback,
                )
            except Exception:
                log.exception(
                    f"Unexpected error occurred while converting '{document}'"
                )
                document.mark_as_failed()

        max_jobs = self.isolation_provider.get_max_parallel_conversions()
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_jobs) as executor:
            executor.map(convert_doc, self.documents)

    def get_unconverted_documents(self) -> List[Document]:
        return [doc for doc in self.documents if doc.is_unconverted()]

    def get_safe_documents(self) -> List[Document]:
        return [doc for doc in self.documents if doc.is_safe()]

    def get_failed_documents(self) -> List[Document]:
        return [doc for doc in self.documents if doc.is_failed()]

    def get_converting_documents(self) -> List[Document]:
        return [doc for doc in self.documents if doc.is_converting()]
