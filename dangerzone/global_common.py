import gzip
import json
import logging
import pathlib
import platform
import shutil
import subprocess
import sys
from typing import Optional

import appdirs
import colorama

from .container import convert
from .settings import Settings
from .util import get_resource_path

log = logging.getLogger(__name__)


class GlobalCommon(object):
    """
    The GlobalCommon class is a singleton of shared functionality throughout the app
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
