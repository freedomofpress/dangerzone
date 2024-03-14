import pathlib
import platform
import subprocess
from pathlib import Path

import pytest

from dangerzone.isolation_provider.dummy import Dummy
from dangerzone.logic import DangerzoneCore
from dangerzone.util import get_tessdata_dir


def test_ocr_ommisions() -> None:
    # Grab the languages that are available in the Tesseract data dir.
    tessdata_dir = pathlib.Path(get_tessdata_dir())
    suffix_len = len(".traineddata")
    available_langs = {f.name[:-suffix_len] for f in tessdata_dir.iterdir()}

    # Grab the languages that Dangerzone offers to the user through the GUI/CLI.
    offered_langs = set(DangerzoneCore(Dummy()).ocr_languages.values())

    # Ensure that both the available languages and the ones we offer to the user are the
    # same.
    assert available_langs == offered_langs
