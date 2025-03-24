import platform
import sys
import typing
import zipfile
from pathlib import Path
from typing import Callable, List

import pytest
from pytest_mock import MockerFixture

from dangerzone.document import SAFE_EXTENSION
from dangerzone.gui import Application

sys.dangerzone_dev = True  # type: ignore[attr-defined]


# Use this fixture to make `pytest-qt` invoke our custom QApplication.
# See https://pytest-qt.readthedocs.io/en/latest/qapplication.html#testing-custom-qapplications
@pytest.fixture(scope="session")
def qapp_cls() -> typing.Type[Application]:
    return Application


@pytest.fixture
def unreadable_pdf(tmp_path: Path) -> str:
    file_path = tmp_path / "document.pdf"
    file_path.touch(mode=0o000)
    return str(file_path)


@pytest.fixture
def pdf_11k_pages(tmp_path: Path) -> str:
    """11K page document with pages of 1x1 px. Generated with the command:

    gs -sDEVICE=pdfwrite -o sample-11k-pages.pdf -dDEVICEWIDTHPOINTS=1 -dDEVICEHEIGHTPOINTS=1 -c 11000 {showpage} repeat
    """

    filename = "sample-11k-pages.pdf"
    zip_path = test_docs_compressed_dir / f"{filename}.zip"
    with zipfile.ZipFile(zip_path, "r") as zip_file:
        zip_file.extractall(tmp_path)
    return str(tmp_path / filename)


@pytest.fixture
def uncommon_text() -> str:
    """Craft a string with Unicode characters that are considered not common.

    Create a string that contains the following uncommon characters:

    * ANSI escape sequences: \033[31;1;4m and \033[0m
    * A Unicode character that resembles an English character: greek "X" (U+03A7)
    * A Unicode control character that is not part of ASCII: zero-width joiner
      (U+200D)
    * An emoji: Cross Mark (U+274C)
    * A surrogate escape used to decode an invalid UTF-8 sequence 0xF0 (U+DCF0)
    """
    return "\033[31;1;4m BaD TeΧt \u200d ❌ \udcf0 \033[0m"


@pytest.fixture
def uncommon_filename(uncommon_text: str) -> str:
    """Craft a filename with Unicode characters that are considered not common.

    We reuse the same uncommon string as above, with a small exception for macOS and
    Windows.

    Because the NTFS filesystem in Windows and APFS filesystem in macOS accept only
    UTF-8 encoded strings [1], we cannot create a filename with invalid Unicode
    characters. So, in order to test the rest of the corner cases, we replace U+DCF0
    with an empty string.

    Windows has the extra restriction that it cannot have escape characters in
    filenames, so we replace the ASCII Escape character (\033 / U+001B) as well.

    [1]: https://en.wikipedia.org/wiki/Filename#Comparison_of_filename_limitations
    """
    if platform.system() == "Darwin":
        uncommon_text = uncommon_text.replace("\udcf0", "")
    elif platform.system() == "Windows":
        uncommon_text = uncommon_text.replace("\udcf0", "").replace("\033", "")
    return uncommon_text + ".pdf"


@pytest.fixture
def sanitized_text() -> str:
    """Return a sanitized version of the uncommon_text.

    Take the uncommon text string and replace all the control/invalid characters with
    "�". The rest of the characters (emojis and non-English leters) are retained as is.
    """
    return "�[31;1;4m BaD TeΧt � ❌ � �[0m"


@pytest.fixture
def sample_doc() -> str:
    return str(test_docs_dir.joinpath(BASIC_SAMPLE_DOC))


@pytest.fixture
def sample_bad_height() -> str:
    return str(test_docs_dir.joinpath("sample_bad_max_height.pdf"))


@pytest.fixture
def sample_bad_width() -> str:
    return str(test_docs_dir.joinpath("sample_bad_max_width.pdf"))


@pytest.fixture
def sample_pdf() -> str:
    return str(test_docs_dir.joinpath(BASIC_SAMPLE_PDF))


@pytest.fixture
def mock_settings(mocker: MockerFixture, tmp_path: Path) -> Path:
    mocker.patch("dangerzone.settings.FILENAME", tmp_path / "settings.json")
    return tmp_path


@pytest.fixture
def default_settings_0_4_1() -> dict:
    """Get the default settings for the 0.4.1 Dangerzone release."""
    return {
        "save": True,
        "archive": True,
        "ocr": True,
        "ocr_language": "English",
        "open": True,
        "open_app": None,
        "safe_extension": "-safe.pdf",
    }


SAMPLE_DIRECTORY = "test_docs"
BASIC_SAMPLE_PDF = "sample-pdf.pdf"
BASIC_SAMPLE_DOC = "sample-doc.doc"
SAMPLE_EXTERNAL_DIRECTORY = "test_docs_external"
SAMPLE_COMPRESSED_DIRECTORY = "test_docs_compressed"

test_docs_dir = Path(__file__).parent.joinpath(SAMPLE_DIRECTORY)
test_docs_compressed_dir = Path(__file__).parent.joinpath(SAMPLE_COMPRESSED_DIRECTORY)

test_docs = [
    p
    for p in test_docs_dir.rglob("*")
    if p.is_file()
    and not (p.name.endswith(SAFE_EXTENSION) or p.name.startswith("sample_bad"))
]

# Pytest parameter decorators
for_each_doc = pytest.mark.parametrize(
    "doc", test_docs, ids=[str(doc.name) for doc in test_docs]
)


# External Docs - base64 docs encoded for externally sourced documents
# XXX to reduce the chance of accidentally opening them
test_docs_external_dir = Path(__file__).parent.joinpath(SAMPLE_EXTERNAL_DIRECTORY)


def get_docs_external(pattern: str = "*") -> List[Path]:
    if not pattern.endswith("*"):
        pattern = f"{pattern}.b64"
    return [
        p
        for p in test_docs_external_dir.rglob(pattern)
        if p.is_file() and not (p.name.endswith(SAFE_EXTENSION))
    ]


# Pytest parameter decorators
def for_each_external_doc(glob_pattern: str = "*") -> Callable:
    test_docs_external = get_docs_external(glob_pattern)
    return pytest.mark.parametrize(
        "doc",
        test_docs_external,
        ids=[str(doc.name).rstrip(".b64") for doc in test_docs_external],
    )


class TestBase:
    sample_doc = str(test_docs_dir.joinpath(BASIC_SAMPLE_PDF))
