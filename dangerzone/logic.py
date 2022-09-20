import gzip
import json
import logging
import pathlib
import platform
import shutil
import subprocess
import sys
from typing import Callable, List, Optional

import appdirs
import colorama

from .container import convert
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

    def add_document(
        self, input_filename: str, output_filename: Optional[str] = None
    ) -> None:
        doc = Document(input_filename, output_filename)
        self.documents.append(doc)

    def convert_documents(
        self, ocr_lang: Optional[str], stdout_callback: Callable[[str], None]
    ) -> None:
        all_successful = True

        for document in self.documents:
            success = convert(
                document.input_filename,
                document.output_filename,
                ocr_lang,
                stdout_callback,
            )
            if success:
                document.mark_as_safe()
            else:
                document.mark_as_failed()

    def get_safe_documents(self) -> List[Document]:
        return [doc for doc in self.documents if doc.is_safe()]

    def get_failed_documents(self) -> List[Document]:
        return [doc for doc in self.documents if doc.is_failed()]
