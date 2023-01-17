import gzip
import json
import logging
import pathlib
import platform
import shutil
import subprocess
import sys
import traceback
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Callable, Dict, List, Optional

import appdirs
import colorama

from . import container, errors
from .document import Document
from .settings import Settings
from .util import get_resource_path

log = logging.getLogger(__name__)


class DangerzoneCore(object):
    """
    Singleton of shared state / functionality throughout the app
    """

    def __init__(self) -> None:
        # Initialize terminal colors
        colorama.init(autoreset=True)

        # App data folder
        self.appdata_path = appdirs.user_config_dir("dangerzone")

        # Languages supported by tesseract
        with open(get_resource_path("ocr-languages.json"), "r") as f:
            self.ocr_languages = json.load(f)

        # Load settings
        self.settings = Settings(self)

        self.documents: List[Document] = []

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

    def convert_documents(
        self, ocr_lang: Optional[str], stdout_callback: Optional[Callable] = None
    ) -> None:
        def convert_doc(document: Document) -> None:
            success = container.convert(
                document,
                ocr_lang,
                stdout_callback,
            )

        max_jobs = container.get_max_parallel_conversions()
        with ThreadPoolExecutor(max_workers=max_jobs) as executor:
            conversions: Dict[Document, Future] = {}

            # Start all parallel conversions
            for document in self.get_unconverted_documents():
                conversion = executor.submit(convert_doc, document)
                conversions[document] = conversion

            # Check the results to raise any exceptions that may have happened
            for document in conversions:
                try:
                    conversion = conversions[document]
                    conversion.result()
                except Exception as e:
                    log.error(
                        f"Something unexpected happened when converting document '{document.id}': {e}"
                    )
                    traceback.print_exception(type(e), e, e.__traceback__)

    def get_unconverted_documents(self) -> List[Document]:
        return [doc for doc in self.documents if doc.is_unconverted()]

    def get_safe_documents(self) -> List[Document]:
        return [doc for doc in self.documents if doc.is_safe()]

    def get_failed_documents(self) -> List[Document]:
        return [doc for doc in self.documents if doc.is_failed()]

    def get_converting_documents(self) -> List[Document]:
        return [doc for doc in self.documents if doc.is_converting()]
